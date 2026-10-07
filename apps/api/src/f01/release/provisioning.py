"""Explicit owner-requested, correlated provider project setup. No blind create retry."""
import asyncio
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from f01.application import releases as service
from f01.application.execution import now
from f01.config import Settings
from f01.db import models as db
from f01.db.session import Database
from f01.domain.errors import ApplicationError
from f01.release.provider import TargetProvider, ReleaseProviderError


class TargetWorker:
    def __init__(self, database: Database, settings: Settings, provider: TargetProvider) -> None:
        self.database, self.settings, self.provider = database, settings, provider

    async def run_once(self) -> bool:
        with self.database.session() as session, session.begin():
            row = session.scalar(select(db.TargetProvisioning).where(db.TargetProvisioning.state.in_(('queued', 'creating', 'reconciling')), db.TargetProvisioning.attempts < 60,
                (db.TargetProvisioning.lease_until.is_(None)) | (db.TargetProvisioning.lease_until <= now())).order_by(db.TargetProvisioning.created_at).with_for_update(skip_locked=True).limit(1))
            if row is None:
                return False
            row.epoch += 1
            row.attempts += 1
            row.lease_token, row.lease_until = uuid4(), now()+timedelta(seconds=45)
            identifier, token, name, state, pid = row.id, row.lease_token, row.provider_name, row.state, row.project_id
            project = session.get(db.Project, pid)
            assert project
            authenticated = True
            if row.auth_session_id:
                auth = session.get(db.AuthSession, row.auth_session_id)
                authenticated = bool(auth and auth.user_id == row.user_id and not auth.revoked_at and auth.expires_at > now() and auth.last_seen_at+timedelta(seconds=self.settings.session_idle_seconds) > now())
            elif self.settings.auth_mode == 'oidc':
                authenticated = False
            if state == 'queued' and (not authenticated or project.archived_at or project.current_version_id != row.version_id or project.current_brain_revision_id != row.brain_revision_id or row.deadline_at <= now()):
                row.state, row.error_code = 'failed', 'RELEASE_STALE_CONTEXT' if authenticated else 'AUTHENTICATION_REQUIRED'
                return True
        try:
            async with asyncio.timeout(35):
                found = await self.provider.find_target(name)
                if state == 'queued':
                    if found:
                        raise ReleaseProviderError('RELEASE_TARGET_NAME_CONFLICT')
                    with self.database.session() as session, session.begin():
                        saved = session.get(db.TargetProvisioning, identifier, with_for_update=True)
                        assert saved
                        if saved.lease_token != token:
                            return True
                        saved.state = 'creating'
                    found = await self.provider.create_target(name)
                if found:
                    service.configure(self.database, pid, found.project_id, found.team_id, found.public_url, self.settings.factory_origin)
                    with self.database.session() as session, session.begin():
                        saved = session.get(db.TargetProvisioning, identifier, with_for_update=True)
                        assert saved
                        if saved.lease_token == token:
                            saved.state, saved.error_code = 'ready', None
                else:
                    raise ReleaseProviderError('RELEASE_PROVIDER_OUTCOME_UNKNOWN', uncertain=True)
        except (ReleaseProviderError, ApplicationError) as exc:
            with self.database.session() as session, session.begin():
                saved = session.get(db.TargetProvisioning, identifier, with_for_update=True)
                assert saved
                if saved.lease_token == token:
                    # Once create may have dispatched, only observation can resolve it.
                    saved.state = 'reconciling' if saved.state != 'queued' or isinstance(exc, ReleaseProviderError) and exc.uncertain else 'failed'
                    saved.error_code = exc.code
        except Exception:
            with self.database.session() as session, session.begin():
                saved = session.get(db.TargetProvisioning, identifier, with_for_update=True)
                assert saved
                if saved.lease_token == token:
                    saved.state, saved.error_code = 'reconciling', 'RELEASE_RECOVERY_REQUIRED'
        finally:
            with self.database.session() as session, session.begin():
                saved = session.get(db.TargetProvisioning, identifier, with_for_update=True)
                if saved and saved.lease_token == token:
                    saved.lease_token, saved.lease_until = None, now()+timedelta(seconds=5)
        return True
