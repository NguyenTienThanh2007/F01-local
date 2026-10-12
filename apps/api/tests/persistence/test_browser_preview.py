"""Local storage preview boundaries; controlled fetch is not Docker acceptance."""
import asyncio
from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from f01.application import execution as service
from f01.application.projects import workspace
from f01.config import Settings
from f01.db.models import IsolatedPreview
from f01.db.session import Database
from f01.domain.planning import ProjectPlan
from f01.execution.preview_gateway import create_gateway
from f01.execution.preview_origin import browser_origin
from f01.execution.worker import BuildWorker
from tests.persistence.test_phase2b import ControlledSandbox, SourceProvider, setup_build


def test_browser_preview_keeps_project_origin_and_embedded_isolation(
    database: Database, project_settings: Settings, project_plan: ProjectPlan,
) -> None:
    configured = project_settings.model_copy(update={
        'real_execution_enabled': True, 'execution_mode': 'real',
        'sandbox_image_id': 'sha256:' + 'a' * 64,
        'preview_origin': 'http://localhost:3031', 'factory_origin': 'http://127.0.0.1:3000',
        'local_browser_preview_enabled': True,
        'planning_daily_token_budget': 10000000, 'planning_requests_per_minute': 30,
    })
    owner, pid, body = setup_build(database, configured, project_plan)
    service.queue(database, configured, owner, pid, body, 'browser-preview')
    asyncio.run(BuildWorker(database, configured, ControlledSandbox(), SourceProvider()).run_once())
    saved = workspace(database, owner, pid)
    assert saved.current_version is not None
    descriptor = saved.current_version.preview_descriptor
    assert descriptor.kind == 'isolated' and descriptor.browser_url is not None
    assert descriptor.browser_url == descriptor.url.replace(configured.preview_origin, browser_origin(configured, pid) or '')
    assert browser_origin(configured, pid) != browser_origin(configured, uuid4())
    assert browser_origin(configured.model_copy(update={'local_browser_preview_enabled': False}), pid) is None
    assert browser_origin(configured.model_copy(update={'app_env': 'production'}), pid) is None

    class Fetch:
        calls = 0
        async def fetch(self, name: str, target: str, alive: object) -> tuple[int, str, bytes]:
            self.calls += 1
            return 200, 'text/html', b'<html>Storage diagnostic</html>'

    fetch = Fetch()
    app = create_gateway(configured)
    with TestClient(app) as gateway:
        app.state.sandbox = fetch
        shared = gateway.get(descriptor.url)
        assert shared.status_code == 200
        assert 'sandbox allow-scripts;' in shared.headers['Content-Security-Policy']
        assert 'allow-same-origin' not in shared.headers['Content-Security-Policy']
        native = gateway.get(descriptor.browser_url, headers={'Cookie': 'factory_secret=never-forward', 'Authorization': 'Bearer never-forward'})
        assert native.status_code == 200
        policy = native.headers['Content-Security-Policy']
        assert 'sandbox allow-scripts allow-same-origin;' in policy
        assert "frame-ancestors 'none'" in policy
        assert "worker-src 'none'" in policy and "connect-src http://f01-" in policy
        assert 'set-cookie' not in native.headers
        for rejected in (
            descriptor.browser_url.replace(pid.hex, uuid4().hex),
            descriptor.browser_url.replace('.localhost', '.example.com'),
            descriptor.browser_url.replace(descriptor.browser_url.split('/')[-2], 'x' * 43),
        ):
            assert gateway.get(rejected).status_code == 404
        assert fetch.calls == 2, 'Rejected hosts and capabilities must never reach Docker.'
        app.state.settings = configured.model_copy(update={'local_browser_preview_enabled': False})
        assert gateway.get(descriptor.browser_url).status_code == 404
        assert gateway.get(descriptor.url).status_code == 200
        app.state.settings = configured
        with database.session() as session, session.begin():
            row = session.get(IsolatedPreview, descriptor.preview_id)
            assert row is not None
            row.expires_at = service.now() - timedelta(seconds=1)
        assert gateway.get(descriptor.browser_url).status_code == 404
        assert gateway.get(descriptor.url).status_code == 404


@pytest.mark.parametrize('change', [{'app_env': 'production'}, {'factory_origin': 'http://localhost:3000'}, {'preview_origin': 'https://preview.example.com'}, {'real_execution_enabled': False}])
def test_local_browser_preview_cannot_enable_unsafe_configuration(settings: Settings, change: dict[str, object]) -> None:
    from pydantic import ValidationError
    values = settings.model_dump()
    values.update(local_browser_preview_enabled=True, real_execution_enabled=True,
                  preview_origin='http://localhost:3031', factory_origin='http://127.0.0.1:3000')
    values.update(change)
    with pytest.raises(ValidationError, match='Local browser previews'):
        Settings(**values, _env_file=None)
