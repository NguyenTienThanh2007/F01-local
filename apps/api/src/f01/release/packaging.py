"""Production packages are built only in accepted isolated Docker containers."""
import asyncio
import base64
import json
import secrets
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
from f01.domain.execution import CommandEvidence
from f01.execution.docker import DockerSandbox, SandboxError
from f01.release.package import validate_package, package_digest


class PackagingWorker:
    def __init__(self, database: Database, settings: Settings, sandbox: DockerSandbox) -> None:
        self.database, self.settings, self.sandbox = database, settings, sandbox

    def claim(self) -> tuple[UUID, UUID, str] | None:
        with self.database.session() as session, session.begin():
            row = session.scalar(select(db.ArtifactPreparation).where(db.ArtifactPreparation.state.in_(('queued', 'packaging')),
                (db.ArtifactPreparation.lease_until.is_(None)) | (db.ArtifactPreparation.lease_until <= now())).order_by(db.ArtifactPreparation.created_at).with_for_update(skip_locked=True).limit(1))
            if row is None:
                return None
            # Cleanup identity is retained until observed removal; do not reuse a stale container.
            row.epoch += 1
            row.lease_token, row.lease_until = uuid4(), now()+timedelta(seconds=30)
            row.state = 'packaging'
            return row.id, row.lease_token, row.container_name or ''

    async def run_once(self) -> bool:
        claimed = await asyncio.to_thread(self.claim)
        if not claimed:
            return False
        identifier, token, prior = claimed
        name = ''
        error: str | None = None
        try:
            if prior:
                await self.sandbox.remove(prior)
            with self.database.session() as session, session.begin():
                row = session.get(db.ArtifactPreparation, identifier, with_for_update=True)
                assert row is not None
                if row.lease_token != token:
                    return True
                project = session.get(db.Project, row.project_id)
                assert project is not None
                if row.deadline_at <= now():
                    raise ApplicationError('RELEASE_DEADLINE_EXCEEDED')
                if project.archived_at or project.current_version_id != row.version_id or project.current_brain_revision_id != row.brain_revision_id:
                    raise ApplicationError('RELEASE_STALE_CONTEXT')
                _, config = service.configured(session, project.id, row.configuration_id)
                version, candidate, source, evidence = service.source_for_version(session, project.id, row.version_id)
                name = self.sandbox.name(identifier, row.epoch, 0)
                row.container_name = name
                marker = {'preparation_id': str(identifier), 'source_digest': source.digest, 'version_id': str(version.id), 'configuration_digest': config.digest}
                manifest: dict[str, object] = {'schema_version': 1, 'profile': 'next-static-v1', 'project_id': str(project.id), 'candidate_id': str(candidate.id),
                    'version_id': str(version.id), 'brain_revision_id': str(version.brain_revision_id), 'request_id': str(source.lineage.request_id), 'plan_id': str(source.lineage.plan_id),
                    'source_digest': source.digest, 'parent_digest': source.parent_digest, 'configuration_id': str(config.id), 'configuration_digest': config.digest,
                    'source_lineage': source.lineage.model_dump(mode='json'), 'source_evidence': [{'id': str(e.id), 'digest': service.fingerprint(e.content)} for e in evidence],
                    'image_id': self.sandbox.image, 'marker': marker, 'migration_mode': 'none', 'data_schema': 'none', 'external_effects': 'none'}
            async def alive() -> bool:
                with self.database.session() as session, session.begin():
                    row = session.get(db.ArtifactPreparation, identifier, with_for_update=True)
                    if not row or row.lease_token != token or row.lease_until is None or row.lease_until <= now() or row.deadline_at <= now():
                        return False
                    row.lease_until = now()+timedelta(seconds=30)
                    return True
            await self.sandbox.ready()
            await self.sandbox.create(name, source.lineage.project_id, identifier, '/p/'+str(uuid4())+'/'+secrets.token_urlsafe(32))
            materialized = await self.sandbox.materialize(name, source, alive)
            if materialized.exit_code:
                raise ApplicationError('RELEASE_PACKAGE_INVALID')
            raw = await self.sandbox.exec(name, ('/usr/local/bin/node', '/opt/f01/production.mjs', self.sandbox.source_argument(source), base64.b64encode(json.dumps(marker).encode()).decode()), 250, alive, limit=24000000)
            result = json.loads(raw)
            if result.get('error') in {'PRODUCTION_CONFIGURATION_FAILED','PRODUCTION_INSTALL_FAILED','PRODUCTION_TYPECHECK_FAILED','PRODUCTION_BUILD_FAILED','PRODUCTION_TEST_FAILED','PRODUCTION_INTEGRITY_FAILED','PRODUCTION_EXPORT_FAILED'}:
                raise ApplicationError(result['error'])
            package = result['package']
            if not isinstance(package, dict):
                raise ApplicationError('RELEASE_PACKAGE_INVALID')
            files = validate_package(package)
            checks = [CommandEvidence.model_validate({**item, 'image_id': self.sandbox.image}) for item in result['evidence']]
            if {c.phase for c in checks} != {'install', 'typecheck', 'build', 'test'} or any(c.exit_code for c in checks) or result['platform'] != 'linux' or result['architecture'] not in ('arm64', 'x64'):
                raise ApplicationError('RELEASE_VERIFICATION_REQUIRED')
            for field in ('lock_digest', 'configuration_digest'):
                if not isinstance(result[field], str) or len(result[field]) != 64:
                    raise ApplicationError('RELEASE_PACKAGE_INVALID')
            await self.sandbox.exec(name, ('/usr/local/bin/node', '/opt/f01/static-serve.mjs'), 10, alive)
            for _ in range(40):
                try:
                    status, _, content = await self.sandbox.fetch(name, '/__f01_release.json', alive)
                    if status == 200 and json.loads(content) == marker:
                        break
                except SandboxError:
                    pass
                await asyncio.sleep(.25)
            else:
                raise ApplicationError('RELEASE_HEALTH_FAILED')
            status, _, html = await self.sandbox.fetch(name, '/', alive)
            if status != 200 or html != next(f.data for f in files if f.path == '.vercel/output/static/index.html'):
                raise ApplicationError('RELEASE_HEALTH_FAILED')
            manifest.update(lock_digest=result['lock_digest'], production_configuration_digest=result['configuration_digest'], target_os=result['platform'], target_architecture=result['architecture'],
                production_evidence=[materialized.model_dump(mode='json'), *[c.model_dump(mode='json') for c in checks]], output_digest=package_digest(files), production_health='passed')
            # Release credentials exist only in the independent release worker process.
            with self.database.session() as session, session.begin():
                row = session.get(db.ArtifactPreparation, identifier, with_for_update=True)
                assert row is not None
                project = session.get(db.Project, row.project_id, with_for_update=True)
                assert project is not None
                if row.lease_token != token or row.deadline_at <= now() or project.archived_at or project.current_version_id != row.version_id or project.current_brain_revision_id != row.brain_revision_id:
                    raise ApplicationError('RELEASE_STALE_CONTEXT')
                artifact_id = uuid4()
                session.add(db.ReleaseArtifact(id=artifact_id, project_id=row.project_id, preparation_id=row.id, candidate_id=candidate.id, version_id=row.version_id,
                    brain_revision_id=row.brain_revision_id, configuration_id=row.configuration_id, digest=package_digest(files), package=package, manifest=manifest, created_at=now()))
                row.artifact_id, row.state = artifact_id, 'succeeded'
                append_event(session, project, type='release.package_verified', message='Production package verified. Review it before deploying.', actor=project.owner_user_id)
        except (SandboxError, ApplicationError) as exc:
            error = exc.code
        except Exception:
            error = 'RELEASE_PACKAGING_FAILED'
        finally:
            cleanup = name or prior
            if cleanup:
                try:
                    await self.sandbox.remove(cleanup)
                    cleanup = ''
                except SandboxError:
                    pass
            with self.database.session() as session, session.begin():
                row = session.get(db.ArtifactPreparation, identifier, with_for_update=True)
                if row and row.lease_token == token:
                    row.container_name = cleanup or None
                    row.lease_token = None
                    row.lease_until = None
                    if error:
                        row.state, row.error_code = 'failed', error
        return True


async def main() -> None:
    from f01.config import get_settings
    import httpx
    settings = get_settings()
    if not settings.release_enabled:
        raise SystemExit('RELEASE_UNAVAILABLE')
    database = Database(settings.database_url)
    try:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket), base_url='http://docker', trust_env=False, timeout=300) as engine:
            worker = PackagingWorker(database, settings, DockerSandbox(engine, settings.production_image_id, lifetime_seconds=1200))
            while True:
                if not await worker.run_once():
                    await asyncio.sleep(1)
    finally:
        database.close()


if __name__ == '__main__':
    asyncio.run(main())
