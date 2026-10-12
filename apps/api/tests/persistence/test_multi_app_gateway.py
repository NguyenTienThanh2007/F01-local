"""The live multi-app runner serves real previews through the actual gateway on loopback."""
from uuid import uuid4

import httpx
import pytest

from f01.config import Settings
from tests.live.multi_app import free_port, preview_settings, serve_preview_gateway


def test_real_preview_gateway_serves_on_loopback_and_rejects_unknown_capabilities(project_settings: Settings) -> None:
    port = free_port()
    settings = preview_settings(project_settings.model_copy(update={'real_execution_enabled': True, 'execution_mode': 'real',
        'sandbox_image_id': 'sha256:' + 'a' * 64, 'sandbox_socket': '/nonexistent/docker.sock'}), port)
    with serve_preview_gateway(settings, port) as origin:
        assert origin == f'http://localhost:{port}'
        response = httpx.get(f'http://127.0.0.1:{port}/p/{uuid4()}/{"a" * 43}/', headers={'Host': f'localhost:{port}'}, trust_env=False)
        assert response.status_code == 404 and response.content == b''
    with pytest.raises(httpx.ConnectError):
        httpx.get(f'http://127.0.0.1:{port}/', trust_env=False, timeout=2)
