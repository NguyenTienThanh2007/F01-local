"""Durable release state machine. Persist pending external writes before dispatch."""
import asyncio
import os
from datetime import timedelta
from uuid import UUID, uuid4
from sqlalchemy import select
from f01.application import releases as service
from f01.application.execution import now
from f01.application.projects import append_event
from f01.config import Settings
from f01.db import models as db
from f01.db.session import Database
from f01.domain.errors import ApplicationError
from f01.release.provider import ReleaseProvider, ReleaseProviderError


class ReleaseWorker:
    def __init__(self, database: Database, settings: Settings, provider: ReleaseProvider) -> None:
        self.database, self.settings, self.provider = database, settings, provider

    def claim(self) -> tuple[UUID, UUID] | None:
        with self.database.session() as session, session.begin():
            row = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.state.not_in(service.TERMINAL), db.ReleaseOperation.attempts < 120,
                db.ReleaseOperation.next_attempt_at <= now(), (db.ReleaseOperation.lease_until.is_(None)) | (db.ReleaseOperation.lease_until <= now()))
                .order_by(db.ReleaseOperation.created_at).with_for_update(skip_locked=True).limit(1))
            if row is None:
                return None
            row.epoch += 1
            row.attempts += 1
            row.lease_token, row.lease_until = uuid4(), now()+timedelta(seconds=45)
            return row.id, row.lease_token

    def save(self, identifier: UUID, token: UUID, *, action: str | None = None, state: str | None = None, error: str | None = None,
             deployment: str | None = None, url: str | None = None, observation: dict[str, object] | None = None, finish: bool = False) -> None:
        with self.database.session() as session, session.begin():
            op = session.get(db.ReleaseOperation, identifier, with_for_update=True)
            if not op or op.lease_token != token or op.lease_until is None or op.lease_until <= now() or op.state in service.TERMINAL:
                raise ApplicationError('RELEASE_LEASE_LOST')
            if action is not None:
                op.action = action
            if state is not None:
                op.state = state
            if error is not None:
                op.error_code = error
            if deployment is not None:
                op.deployment_id = deployment
            if url is not None:
                op.deployment_url = url
            if observation:
                op.last_observed_at = now()
                session.add(db.ReleaseObservation(id=uuid4(), project_id=op.project_id, operation_id=op.id, content=observation, created_at=now()))
            if finish:
                project = session.get(db.Project, op.project_id, with_for_update=True)
                intent = session.get(db.ReleaseIntent, op.release_id)
                assert project and intent
                append_event(session, project, type='release.'+op.state, message='Production release '+op.state+'.', actor=intent.user_id)

    def context(self, identifier: UUID, token: UUID) -> tuple[db.ReleaseOperation, db.ReleaseIntent, db.ReleaseArtifact, db.ReleaseConfiguration, str | None, db.ReleaseArtifact | None]:
        with self.database.session() as session:
            op = session.get(db.ReleaseOperation, identifier)
            assert op is not None
            if op.lease_token != token or op.lease_until is None or op.lease_until <= now():
                raise ApplicationError('RELEASE_LEASE_LOST')
            intent = session.get(db.ReleaseIntent, op.release_id)
            assert intent
            artifact = session.get(db.ReleaseArtifact, intent.artifact_id)
            config = session.get(db.ReleaseConfiguration, intent.configuration_id)
            assert artifact and config
            previous_id: str | None = None
            previous_artifact: db.ReleaseArtifact | None = None
            if intent.previous_release_id:
                previous = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.release_id == intent.previous_release_id))
                prior_intent = session.get(db.ReleaseIntent, intent.previous_release_id)
                assert previous and prior_intent and previous.state == 'succeeded' and previous.deployment_id
                previous_id = previous.deployment_id
                previous_artifact = session.get(db.ReleaseArtifact, prior_intent.artifact_id)
                assert previous_artifact
            return op, intent, artifact, config, previous_id, previous_artifact

    def validate_bases(self, identifier: UUID, token: UUID) -> None:
        with self.database.session() as session, session.begin():
            op = session.get(db.ReleaseOperation, identifier, with_for_update=True)
            assert op
            intent = session.get(db.ReleaseIntent, op.release_id)
            assert intent
            project = session.get(db.Project, intent.project_id, with_for_update=True)
            assert project
            target, _ = service.configured(session, project.id, intent.configuration_id)
            if (op.lease_token != token or op.lease_until is None or op.lease_until <= now()):
                raise ApplicationError('RELEASE_LEASE_LOST')
            if (project.archived_at or project.current_version_id != intent.version_id or project.current_brain_revision_id != intent.brain_revision_id
                or target.generation != intent.target_generation or target.current_release_id != intent.previous_release_id):
                raise ApplicationError('RELEASE_STALE_CONTEXT')
            if intent.auth_session_id:
                auth = session.get(db.AuthSession, intent.auth_session_id)
                if not auth or auth.user_id != intent.user_id or auth.revoked_at or auth.expires_at <= now() or auth.last_seen_at+timedelta(seconds=self.settings.session_idle_seconds) <= now():
                    raise ApplicationError('AUTHENTICATION_REQUIRED')
            elif self.settings.auth_mode == 'oidc':
                raise ApplicationError('AUTHENTICATION_REQUIRED')

    def commit(self, identifier: UUID, token: UUID, url: str) -> None:
        self.validate_bases(identifier, token)
        with self.database.session() as session, session.begin():
            op = session.get(db.ReleaseOperation, identifier, with_for_update=True)
            assert op
            intent = session.get(db.ReleaseIntent, op.release_id)
            assert intent
            project = session.get(db.Project, intent.project_id, with_for_update=True)
            assert project
            target, _ = service.configured(session, project.id, intent.configuration_id)
            if op.lease_token != token or op.lease_until is None or op.lease_until <= now() or target.generation != intent.target_generation or target.current_release_id != intent.previous_release_id:
                raise ApplicationError('RELEASE_LEASE_LOST')
            target.current_release_id, target.generation = intent.id, target.generation+1
            op.state, op.action, op.public_url, op.error_code = 'succeeded', 'done', url, None
            op.last_observed_at = now()
            session.add(db.ReleaseObservation(id=uuid4(), project_id=project.id, operation_id=op.id, content={'kind': 'public_health', 'status': 'passed', 'deployment_id': op.deployment_id}, created_at=now()))
            append_event(session, project, type='release.succeeded', message='Production URL verified and saved.', actor=intent.user_id)

    async def step(self, identifier: UUID, token: UUID) -> None:
        op, intent, artifact, config, previous, previous_artifact = self.context(identifier, token)
        action = op.action
        # Uncertain dispatches remain active even after deadline; they never silently become failed or repeat a write.
        if op.deadline_at <= now() and action not in ('stage_pending', 'promote_pending', 'restore_pending', 'clear_pending', 'restore', 'verify_restore'):
            if action in ('verify_public',):
                self.save(identifier, token, action='restore', state='restoring', error='RELEASE_DEADLINE_EXCEEDED')
            else:
                self.save(identifier, token, state='failed', error='RELEASE_DEADLINE_EXCEEDED', finish=True)
            return
        if op.cancel_requested and action in ('upload', 'stage', 'observe', 'health', 'promote'):
            if op.deployment_id:
                await self.provider.cancel(config, op.deployment_id)
            self.save(identifier, token, state='canceled', finish=True)
            return
        if action == 'upload':
            self.validate_bases(identifier, token)
            await self.provider.upload(config, artifact)
            self.save(identifier, token, action='stage', state='staging')
        elif action == 'stage':
            self.validate_bases(identifier, token)
            self.save(identifier, token, action='stage_pending', state='staging')
            value = await self.provider.stage(config, artifact, str(identifier))
            self.save(identifier, token, action='observe', state='checking', deployment=value.id, url=value.url, observation={'kind': 'staged', 'deployment_id': value.id, 'status': value.state})
        elif action == 'stage_pending':
            found = await self.provider.find(config, artifact, str(identifier))
            if found:
                self.save(identifier, token, action='observe', state='checking', deployment=found.id, url=found.url, observation={'kind': 'reconciled_stage', 'deployment_id': found.id})
            else:
                self.save(identifier, token, state='reconciling', error='RELEASE_PROVIDER_OUTCOME_UNKNOWN')
        elif action == 'observe':
            assert op.deployment_id
            value = await self.provider.observe(config, artifact, str(identifier), op.deployment_id)
            self.save(identifier, token, observation={'kind': 'deployment_status', 'deployment_id': value.id, 'status': value.state})
            if value.state == 'READY':
                self.save(identifier, token, action='health', state='checking')
            elif value.state in ('ERROR', 'CANCELED'):
                self.save(identifier, token, state='failed', error='RELEASE_PROVIDER_DEPLOYMENT_FAILED', finish=True)
        elif action == 'health':
            assert op.deployment_url
            await self.provider.health(op.deployment_url, artifact)
            self.save(identifier, token, action='promote', state='promoting', observation={'kind': 'staged_health', 'status': 'passed'})
        elif action == 'promote':
            self.validate_bases(identifier, token)
            if await self.provider.routing(config) != previous:
                raise ReleaseProviderError('RELEASE_ROUTING_CONFLICT', uncertain=True)
            # Check cancellation/context once more immediately before dispatch.
            latest, *_ = self.context(identifier, token)
            if latest.cancel_requested:
                self.save(identifier, token, state='canceled', finish=True)
                return
            self.validate_bases(identifier, token)
            assert op.deployment_id
            self.save(identifier, token, action='promote_pending', state='promoting')
            await self.provider.promote(config, op.deployment_id)
            self.save(identifier, token, action='verify_public', state='verifying')
        elif action == 'promote_pending':
            routing = await self.provider.routing(config)
            if routing == op.deployment_id:
                self.save(identifier, token, action='verify_public', state='verifying', observation={'kind': 'reconciled_promotion', 'deployment_id': routing})
            else:
                self.save(identifier, token, state='reconciling', error='RELEASE_PROVIDER_OUTCOME_UNKNOWN')
        elif action == 'verify_public':
            routing = await self.provider.routing(config)
            if routing != op.deployment_id:
                self.save(identifier, token, state='reconciling', error='RELEASE_ROUTING_CONFLICT')
                return
            if op.cancel_requested:
                self.save(identifier, token, action='restore', state='restoring', error='RELEASE_CANCELED')
                return
            self.validate_bases(identifier, token)
            await self.provider.health(config.public_url, artifact)
            self.commit(identifier, token, config.public_url)
        elif action == 'restore':
            routing = await self.provider.routing(config)
            if routing == previous:
                self.save(identifier, token, action='verify_restore', state='restoring')
            elif routing == op.deployment_id:
                if previous:
                    self.save(identifier, token, action='restore_pending', state='restoring')
                    await self.provider.promote(config, previous)
                else:
                    self.save(identifier, token, action='clear_pending', state='restoring')
                    assert op.deployment_id
                    await self.provider.clear(config, op.deployment_id)
                self.save(identifier, token, action='verify_restore', state='restoring')
            else:
                self.save(identifier, token, state='reconciling', error='RELEASE_ROUTING_CONFLICT')
        elif action in ('restore_pending', 'clear_pending'):
            if await self.provider.routing(config) == previous:
                self.save(identifier, token, action='verify_restore', state='restoring', observation={'kind': 'reconciled_restore', 'deployment_id': previous})
            else:
                self.save(identifier, token, state='reconciling', error='RELEASE_RESTORE_OUTCOME_UNKNOWN')
        elif action == 'verify_restore':
            if await self.provider.routing(config) != previous:
                self.save(identifier, token, state='reconciling', error='RELEASE_ROUTING_CONFLICT')
                return
            if previous_artifact:
                await self.provider.health(config.public_url, previous_artifact)
            self.save(identifier, token, state='canceled' if op.cancel_requested else 'failed', observation={'kind': 'restored_previous', 'deployment_id': previous, 'status': 'passed'}, finish=True)
        else:
            raise ApplicationError('RELEASE_STATE_INVALID')

    async def run_once(self) -> bool:
        claim = await asyncio.to_thread(self.claim)
        if claim is None:
            return False
        identifier, token = claim
        try:
            async with asyncio.timeout(35):
                await self.step(identifier, token)
        except (ReleaseProviderError, ApplicationError) as exc:
            with self.database.session() as session:
                op = session.get(db.ReleaseOperation, identifier)
                assert op
                action = op.action
            if exc.code == 'RELEASE_LEASE_LOST':
                pass
            elif action in ('promote_pending', 'restore_pending', 'clear_pending', 'stage_pending'):
                # Even a successful response followed by an invalid/failed DB write is an unknown dispatch.
                self.save(identifier, token, state='reconciling', error=exc.code)
            elif action in ('verify_public',):
                if isinstance(exc, ReleaseProviderError) and exc.retryable:
                    self.save(identifier, token, error=exc.code)
                else:
                    self.save(identifier, token, action='restore', state='restoring', error=exc.code)
            elif action in ('restore', 'verify_restore'):
                self.save(identifier, token, state='reconciling', error=exc.code)
            elif isinstance(exc, ReleaseProviderError) and (exc.uncertain or exc.retryable):
                self.save(identifier, token, state='reconciling' if exc.uncertain else None, error=exc.code)
            else:
                self.save(identifier, token, state='failed', error=exc.code, finish=True)
        except (TimeoutError, Exception):
            # Unexpected failure never rewrites a pending external dispatch or the live pointer.
            self.save(identifier, token, state='reconciling', error='RELEASE_RECOVERY_REQUIRED')
        finally:
            with self.database.session() as session, session.begin():
                op = session.get(db.ReleaseOperation, identifier, with_for_update=True)
                if op and op.lease_token == token and op.state not in service.TERMINAL:
                    op.lease_token = op.lease_until = None
                    op.next_attempt_at = now()+timedelta(seconds=min(30, 1+op.attempts//4))
        return True


async def main() -> None:
    import httpx
    from f01.config import get_settings
    from f01.release.vercel import VercelProvider
    from f01.release.provisioning import TargetWorker
    settings = get_settings()
    if not settings.release_enabled:
        raise SystemExit('RELEASE_UNAVAILABLE')
    # Only this independent process reads the release credential. Never pass it to packaging workers.
    token = os.environ.get('F01_VERCEL_TOKEN', '')
    database = Database(settings.database_url)
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=20) as client, httpx.AsyncClient(trust_env=False, timeout=10) as health:
            provider = VercelProvider(client, health, token, settings.factory_origin, os.environ.get('F01_VERCEL_TEAM_ID') or None)
            worker = ReleaseWorker(database, settings, provider)
            targets = TargetWorker(database, settings, provider)
            while True:
                progressed = await targets.run_once()
                if not await worker.run_once() and not progressed:
                    await asyncio.sleep(1)
    finally:
        database.close()


if __name__ == '__main__':
    asyncio.run(main())
