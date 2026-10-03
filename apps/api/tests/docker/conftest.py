"""Explicit opt-in; no skipped Docker test is evidence of containment."""
from collections.abc import Iterator
from f01.db.session import Database
from f01.config import Settings
import os
import pytest
from tests.persistence.conftest import database_url, database, project_settings

def pytest_collection_modifyitems(items:list[pytest.Item])->None:
    if os.environ.get('F01_DOCKER_ACCEPTANCE')!='1':
        for item in items:
            if '/tests/docker/' in str(item.path):item.add_marker(pytest.mark.skip(reason='Real Docker acceptance requires F01_DOCKER_ACCEPTANCE=1 and a provisioned image/socket.'))

@pytest.fixture(autouse=True)
def cleanup_generated_runtimes(database:Database,project_settings:Settings)->Iterator[None]:
    # Runs even after an assertion fails. Only resources recorded in the disposable test DB.
    yield
    import asyncio
    import httpx
    from sqlalchemy import select
    from f01.db.models import ExecutionJob,IsolatedPreview
    from f01.execution.docker import DockerSandbox
    with database.session() as session:
        names=set(session.scalars(select(IsolatedPreview.container_name)).all())|set(session.scalars(select(ExecutionJob.container_name).where(ExecutionJob.container_name.is_not(None))).all())
    async def cleanup()->None:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=os.environ.get('F01_DOCKER_SOCKET','/var/run/docker.sock')),base_url='http://docker',trust_env=False,timeout=30) as client:
            sandbox=DockerSandbox(client,os.environ['F01_SANDBOX_IMAGE_ID'])
            for name in names:
                if name:await sandbox.remove(name)
    if names:asyncio.run(cleanup())
