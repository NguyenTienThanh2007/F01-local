"""Observed live Vercel staging/promote/redeploy/restore; controlled models, real Docker."""
import asyncio
import json
import os
import subprocess
from pathlib import Path
from uuid import UUID, uuid4
import httpx
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from f01.application import execution, releases
from f01.config import Settings
from f01.db import models as db
from f01.db.session import Database
from f01.domain.planning import ProjectPlan
from f01.domain.releases import PrepareRelease, PromoteRelease, SetupReleaseTarget
from f01.execution.docker import DockerSandbox
from f01.execution.worker import BuildWorker
from f01.main import create_app
from f01.release.packaging import PackagingWorker
from f01.release.provisioning import TargetWorker
from f01.release.provider import ReleaseProviderError
from f01.release.vercel import VercelProvider
from f01.release.worker import ReleaseWorker
from tests.persistence.test_phase2a import oidc_settings, login_headers, verifier
from tests.persistence.test_phase2b import SourceProvider, review_plan


def test_live_staged_package_public_release_redeploy_and_restore(database: Database, project_settings: Settings, project_plan: ProjectPlan) -> None:
    root = Path(__file__).resolve().parents[4]
    report_path = root/'.runtime/live-acceptance-report.json'
    report: dict[str, object] = {'provider': 'vercel', 'live_provider': 'not_run', 'model': 'controlled', 'public_health': 'not_run', 'redeploy': 'not_run', 'restore': 'not_run', 'docker_image_id': os.environ['F01_SANDBOX_IMAGE_ID']}
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    image = os.environ['F01_SANDBOX_IMAGE_ID']
    settings = oidc_settings(project_settings).model_copy(update={'release_enabled': True, 'real_execution_enabled': True, 'execution_mode': 'real', 'sandbox_image_id': image,
        'production_image_id': image, 'sandbox_socket': os.environ['F01_DOCKER_SOCKET'], 'planning_daily_token_budget': 10000000, 'planning_requests_per_minute': 30, 'session_idle_seconds': 3600, 'release_timeout_seconds': 600})
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    headers, auth_id = login_headers(database, settings, key)
    app = create_app(settings)
    source = SourceProvider()
    pid: UUID | None = None
    provider_project: str | None = None
    async def work(kind: str) -> None:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket), base_url='http://docker', trust_env=False, timeout=300) as engine:
            sandbox = DockerSandbox(engine, image)
            assert await (BuildWorker(database, settings, sandbox, source).run_once() if kind == 'build' else PackagingWorker(database, settings, sandbox).run_once())
    async def release_ticks(until: str = 'succeeded') -> None:
        async with httpx.AsyncClient(trust_env=False, timeout=20) as client, httpx.AsyncClient(trust_env=False, timeout=10) as health:
            provider = VercelProvider(client, health, os.environ['F01_VERCEL_TOKEN'], settings.factory_origin, os.environ.get('F01_VERCEL_TEAM_ID') or None)
            worker = ReleaseWorker(database, settings, provider)
            for _ in range(160):
                await worker.run_once()
                with database.session() as session:
                    operation = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.project_id == pid).order_by(db.ReleaseOperation.created_at.desc()).limit(1))
                    assert operation
                    if operation.state in releases.TERMINAL:
                        assert operation.state == until, operation.error_code
                        return
                await asyncio.sleep(2)
            raise AssertionError('LIVE_RELEASE_DEADLINE_EXCEEDED')
    try:
        with TestClient(app) as client:
            app.state.oidc_verifier = verifier(settings, key)
            client.headers.update(headers)
            result = client.post('/v1/projects', json={'title': 'Disposable commercial acceptance', 'brief': 'Build a browser-only leads dashboard with local state.'}, headers={'Idempotency-Key': str(uuid4())})
            assert result.status_code == 201
            saved = result.json()
            pid, owner = UUID(saved['project']['id']), UUID(saved['project']['owner_user_id'])
            plan = review_plan(database, settings, project_plan, owner, pid, UUID(saved['request_id']), 'initial')
            result = client.post(f'/v1/projects/{pid}/builds', json=plan.model_dump(mode='json'), headers={'Idempotency-Key': 'live-build-v1'})
            assert result.status_code == 202
            asyncio.run(work('build'))
            first = client.get(f'/v1/projects/{pid}/workspace').json()
            version = first['current_version']
            assert version and version['mode'] == 'real'
            body = SetupReleaseTarget(expected_version_id=UUID(version['id']), expected_brain_revision_id=UUID(version['brain_revision_id']))
            result = client.post(f'/v1/projects/{pid}/release-target', json=body.model_dump(mode='json'), headers={'Idempotency-Key': 'live-hosting'})
            assert result.status_code == 202
            async def target() -> None:
                async with httpx.AsyncClient(trust_env=False, timeout=20) as http, httpx.AsyncClient(trust_env=False, timeout=10) as health:
                    worker = TargetWorker(database, settings, VercelProvider(http, health, os.environ['F01_VERCEL_TOKEN'], settings.factory_origin, os.environ.get('F01_VERCEL_TEAM_ID') or None))
                    for _ in range(5):
                        await worker.run_once()
                        await asyncio.sleep(2)
            asyncio.run(target())
            with database.session() as session:
                setup = session.scalar(select(db.TargetProvisioning).where(db.TargetProvisioning.project_id == pid))
                assert setup and setup.state == 'ready', setup.error_code if setup else 'No saved setup'
                _, config = releases.configured(session, pid)
                provider_project, configuration_id = config.provider_project_id, config.id
                report['provider_project_id'], report['public_url'] = provider_project, config.public_url
            def prepare_and_deploy(current: dict[str, object], key: str) -> UUID:
                version = current['current_version']
                assert isinstance(version, dict)
                preparation = PrepareRelease(version_id=UUID(str(version['id'])), configuration_id=configuration_id, expected_brain_revision_id=UUID(str(version['brain_revision_id'])))
                response = client.post(f'/v1/projects/{pid}/release-artifacts', json=preparation.model_dump(mode='json'), headers={'Idempotency-Key': key+'-package'})
                assert response.status_code == 202
                asyncio.run(work('package'))
                state = releases.workspace(database, settings, owner, pid)
                assert state.preparations[0].state == 'succeeded', state.preparations[0].error_code
                command = PromoteRelease(artifact_id=state.artifacts[0].id, configuration_id=configuration_id, expected_brain_revision_id=state.artifacts[0].brain_revision_id,
                    expected_version_id=state.artifacts[0].version_id, expected_production_release_id=state.current_release_id, expected_target_generation=state.target_generation)
                response = client.post(f'/v1/projects/{pid}/releases', json=command.model_dump(mode='json'), headers={'Idempotency-Key': key})
                assert response.status_code == 202
                assert client.post(f'/v1/projects/{pid}/releases', json=command.model_dump(mode='json'), headers={'Idempotency-Key': key}).json()['id'] == response.json()['id']
                return UUID(response.json()['id'])
            first_release = prepare_and_deploy(first, 'live-v1')
            asyncio.run(release_ticks())
            live_one = releases.workspace(database, settings, owner, pid)
            assert live_one.current_release_id == first_release and live_one.target_generation == 1
            report['public_health'], report['live_provider'] = 'passed', 'passed'
            report['release_v1'], report['artifact_v1'] = str(first_release), live_one.artifacts[0].digest
            report_path.write_text(json.dumps(report, indent=2)+'\n')
            result = client.post(f'/v1/projects/{pid}/requests', json={'text': 'Add a priority filter to the existing leads dashboard.', 'base_brain_revision_id': first['project']['current_brain_revision_id'], 'base_version_id': first['project']['current_version_id']}, headers={'Idempotency-Key': 'live-modify'})
            assert result.status_code == 201
            plan = review_plan(database, settings, project_plan, owner, pid, UUID(result.json()['id']), 'change')
            assert client.post(f'/v1/projects/{pid}/builds', json=plan.model_dump(mode='json'), headers={'Idempotency-Key': 'live-rebuild'}).status_code == 202
            asyncio.run(work('build'))
            second = client.get(f'/v1/projects/{pid}/workspace').json()
            assert second['current_version']['id'] != first['current_version']['id']
            assert releases.workspace(database, settings, owner, pid).current_release_id == first_release
            second_release = prepare_and_deploy(second, 'live-v2')
            asyncio.run(release_ticks())
            live_two = releases.workspace(database, settings, owner, pid)
            assert live_two.current_release_id == second_release and live_two.target_generation == 2 and len(live_two.releases) == 2
            report['redeploy'], report['release_v2'], report['artifact_v2'] = 'passed', str(second_release), live_two.artifacts[0].digest
            assert live_two.configuration is not None
            subprocess.run(['node',str(root/'apps/web/tests/public-release-probe.mjs'),live_two.configuration.public_url,json.dumps(live_two.artifacts[0].manifest['marker']),'priority'],check=True,capture_output=True,timeout=60)
            report['public_browser'] = 'passed'
            # Explicitly prove retained old package restoration through the same provider primitive, then restore v2.
            async def restore() -> None:
                with database.session() as session:
                    _, configuration = releases.configured(session, pid)
                    old = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.release_id == first_release))
                    new = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.release_id == second_release))
                    assert old and new and old.deployment_id and new.deployment_id
                    old_package = session.get(db.ReleaseArtifact, live_one.artifacts[0].id)
                    new_package = session.get(db.ReleaseArtifact, live_two.artifacts[0].id)
                    assert old_package and new_package
                async with httpx.AsyncClient(trust_env=False, timeout=20) as http, httpx.AsyncClient(trust_env=False, timeout=10) as health:
                    provider = VercelProvider(http, health, os.environ['F01_VERCEL_TOKEN'], settings.factory_origin)
                    for operation, artifact in ((old, old_package), (new, new_package)):
                        assert operation.deployment_id
                        await provider.promote(configuration, operation.deployment_id)
                        for _ in range(60):
                            if await provider.routing(configuration) == operation.deployment_id:
                                try:
                                    await provider.health(configuration.public_url, artifact)
                                    break
                                except ReleaseProviderError:
                                    pass
                            await asyncio.sleep(2)
                        else:
                            raise AssertionError('LIVE_RESTORE_HEALTH_FAILED')
            asyncio.run(restore())
            report['restore'], report['versions_history'] = 'passed', 'passed'
            report_path.write_text(json.dumps(report, indent=2)+'\n')
    except Exception:
        report['acceptance'] = 'failed'
        report_path.write_text(json.dumps(report, indent=2)+'\n')
        raise
    finally:
        async def cleanup() -> None:
            with database.session() as session:
                names = set(session.scalars(select(db.IsolatedPreview.container_name))) | set(session.scalars(select(db.ExecutionJob.container_name))) | set(session.scalars(select(db.ArtifactPreparation.container_name)))
            async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket), base_url='http://docker', trust_env=False, timeout=30) as engine:
                for name in names:
                    if name:
                        await DockerSandbox(engine, image).remove(name)
            # This project was created only by this acceptance test. Remove its disposable live resources.
            if provider_project:
                assert pid is not None
                async with httpx.AsyncClient(trust_env=False, timeout=20) as http, httpx.AsyncClient() as health:
                    with database.session() as session:
                        _, config = releases.configured(session, pid)
                    await VercelProvider(http, health, os.environ['F01_VERCEL_TOKEN'], settings.factory_origin).request(config, 'DELETE', '/v9/projects/'+provider_project)
                    report['disposable_provider_cleanup'] = 'passed'
                    report_path.write_text(json.dumps(report, indent=2)+'\n')
        asyncio.run(cleanup())
