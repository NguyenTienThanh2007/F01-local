"""Actual isolated production packaging; no Vercel or paid model calls."""
import asyncio
import os
from uuid import uuid4
import httpx
from sqlalchemy import select
from f01.application import execution, releases
from f01.application.projects import workspace
from f01.config import Settings
from f01.db import models as db
from f01.db.session import Database
from f01.domain.planning import ProjectPlan
from f01.domain.releases import PrepareRelease
from f01.execution.docker import DockerSandbox
from f01.execution.worker import BuildWorker
from f01.release.packaging import PackagingWorker
from f01.release.package import validate_package
from tests.persistence.test_phase2b import setup_build, SourceProvider


def test_docker_production_packaging_exact_source_and_root_path(database: Database, project_settings: Settings, project_plan: ProjectPlan) -> None:
    image = os.environ['F01_SANDBOX_IMAGE_ID']
    assert os.environ.get('F01_CONTAINMENT_VERIFIED_ID') == image
    settings = project_settings.model_copy(update={'real_execution_enabled': True, 'release_enabled': True, 'execution_mode': 'real', 'sandbox_image_id': image,
        'production_image_id': image, 'sandbox_socket': os.environ.get('F01_DOCKER_SOCKET', '/var/run/docker.sock'), 'planning_daily_token_budget': 10000000})
    owner, pid, command = setup_build(database, settings, project_plan)
    execution.queue(database, settings, owner, pid, command, 'production-source')
    async def build() -> None:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket), base_url='http://docker', trust_env=False, timeout=300) as engine:
            assert await BuildWorker(database, settings, DockerSandbox(engine, image), SourceProvider()).run_once()
    asyncio.run(build())
    saved = workspace(database, owner, pid)
    assert saved.current_version
    config = releases.configure(database, pid, 'prj_'+pid.hex, None, 'https://f01-'+pid.hex+'.vercel.app', settings.factory_origin)
    prepared = releases.prepare(database, settings, owner, pid, PrepareRelease(version_id=saved.current_version.id, configuration_id=config,
        expected_brain_revision_id=saved.project.current_brain_revision_id), 'production-package')
    async def package() -> None:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket), base_url='http://docker', trust_env=False, timeout=300) as engine:
            assert await PackagingWorker(database, settings, DockerSandbox(engine, image)).run_once()
    asyncio.run(package())
    state = releases.workspace(database, settings, owner, pid)
    assert state.preparations[0].state == 'succeeded', state.preparations[0].error_code
    artifact = state.artifacts[0]
    assert artifact.version_id == saved.current_version.id and artifact.manifest['image_id'] == image
    assert artifact.manifest['production_health'] == 'passed'
    assert workspace(database, owner, pid).preview == saved.preview
    with database.session() as session:
        stored = session.get(db.ReleaseArtifact, artifact.id)
        assert stored
        files = validate_package(stored.package, stored.digest)
        assert any(f.path == '.vercel/output/static/index.html' for f in files)
        assert all(b'/p/' not in f.data for f in files)
        candidate = session.get(db.SourceCandidate, artifact.candidate_id)
        assert candidate and artifact.manifest['source_digest'] == candidate.digest
    assert prepared.id == state.preparations[0].id
