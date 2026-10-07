"""Run persisted browser acceptance with disposable PostgreSQL and controlled providers."""
from pathlib import Path
import os, subprocess, time, tempfile, shutil, socket, sys
import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
root = Path(__file__).resolve().parents[1]
if sys.argv[1:] not in ([], ['--phase1'], ['--phase2a'], ['--ux0'], ['--commercial']):
    raise SystemExit('Usage: test-m5.py [--phase1|--phase2a|--ux0|--commercial]')
commercial = sys.argv[1:] == ['--commercial']
ux0 = commercial or sys.argv[1:] == ['--ux0']
phase2 = ux0 or sys.argv[1:] == ['--phase2a']
suite = 'test:commercial:e2e' if commercial else 'test:ux0:e2e' if ux0 else 'test:phase2a:e2e' if phase2 else 'test:phase1:e2e' if sys.argv[1:] else 'test:simulation:e2e'
from test_database import test_database, free_port
api_port, web_port = free_port(), free_port()
token = 'synthetic-m5-browser-token-12345678901234567890'
api_process = None
with test_database(root) as database:
    with (root/'.runtime/m5-api.log').open('w') as api_log:
        try:
            config = Config(str(root/'apps/api/alembic.ini')); engine = create_engine(database)
            with engine.begin() as connection:
                config.attributes['connection'] = connection; command.upgrade(config, 'head')
            engine.dispose()
            api_env = dict(os.environ, SIMULATION_RUNNER_ENABLED='false' if ux0 else 'true', SIMULATION_CHANGE_SCENARIO='terminal-failure', SIMULATION_TICK_MS='800', APP_ENV='test', AUTH_MODE='development', EXECUTION_MODE='simulated', REAL_EXECUTION_ENABLED='false', RELEASE_ENABLED='false', DATABASE_URL=database, DEV_API_TOKEN=token, DEV_AUTH_SUBJECT='m5-browser-owner', OPENAI_API_KEY='')
            if phase2:
                from cryptography.fernet import Fernet
                api_env.update(AUTH_MODE='oidc', AUTH_GATEWAY_TOKEN='synthetic-phase2a-gateway-12345678901234567890', SESSION_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                    OIDC_ISSUER=f'http://127.0.0.1:{api_port}/oidc', OIDC_AUTHORIZATION_URL=f'http://127.0.0.1:{api_port}/oidc/authorize',
                    OIDC_TOKEN_URL=f'http://127.0.0.1:{api_port}/oidc/token', OIDC_JWKS_URL=f'http://127.0.0.1:{api_port}/oidc/jwks',
                    OIDC_CLIENT_ID='fixture-client', OIDC_CLIENT_SECRET='synthetic-fixture-client-secret', OIDC_API_AUDIENCE='fixture-api',
                    OIDC_REDIRECT_URI=f'http://127.0.0.1:{web_port}/api/auth/callback', OPENAI_API_KEY='synthetic-phase2a-provider-key',
                    PLANNING_TIMEOUT_SECONDS='10', PLANNING_REQUESTS_PER_MINUTE='20')
            if commercial:
                import json
                accepted = json.loads((root/'.runtime/production-acceptance-report.json').read_text())
                preview_port = free_port()
                api_env.update(EXECUTION_MODE='real', REAL_EXECUTION_ENABLED='true', RELEASE_ENABLED='true',
                    SANDBOX_IMAGE_ID=accepted['image_id'], PRODUCTION_IMAGE_ID=accepted['image_id'],
                    SANDBOX_ACCEPTANCE_REPORT=str(root/'.runtime/production-acceptance-report.json'), PRODUCTION_ACCEPTANCE_REPORT=str(root/'.runtime/production-acceptance-report.json'),
                    SANDBOX_SOCKET=os.environ.get('F01_DOCKER_SOCKET','/var/run/docker.sock'), PREVIEW_ORIGIN=f'http://localhost:{preview_port}', FACTORY_ORIGIN=f'http://127.0.0.1:{web_port}')
            api_process = subprocess.Popen([str(root/'apps/api/.venv/bin/python'), '-m', 'uvicorn', *(['commercial_browser_fixture:app' if commercial else 'ux0_browser_fixture:app' if ux0 else 'phase2a_browser_fixture:app','--app-dir',str(root/'apps/api/tests')] if phase2 else ['f01.main:app']), '--host', '127.0.0.1', '--port', str(api_port)], cwd=root/'apps/api', env=api_env, stdout=api_log, stderr=api_log)
            import urllib.request
            for _ in range(100):
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{api_port}/v1/health/live').close(); break
                except OSError: time.sleep(.1)
            else: raise RuntimeError('API did not start')
            preview_process = None
            if commercial:
                preview_process = subprocess.Popen([str(root/'apps/api/.venv/bin/python'), '-m', 'uvicorn', 'f01.execution.preview_gateway:app', '--host', '127.0.0.1', '--port', str(preview_port)], cwd=root/'apps/api', env={**api_env, 'F01_PREVIEW_PORT':str(preview_port)}, stdout=api_log, stderr=api_log)
            test_env = dict(os.environ, M5_API_URL=f'http://127.0.0.1:{api_port}', M5_TEST_DATABASE_URL=database, M5_TEST_TOKEN=token)
            if phase2: test_env.update(P2A_WEB_PORT=str(web_port), AUTH_GATEWAY_TOKEN=api_env['AUTH_GATEWAY_TOKEN'], AUTH_MODE='oidc')
            browser = root/'.runtime/browser/extracted/chromium'
            if browser.exists(): test_env['PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH'] = str(browser)
            axe = root/'.runtime/a11y/node_modules/axe-core/axe.min.js'
            if axe.exists(): test_env['M5_AXE_SCRIPT'] = str(axe)
            result = subprocess.run(['pnpm', '--filter', '@f01/web', suite], cwd=root, env=test_env)
        finally:
            if commercial and 'preview_process' in locals() and preview_process: preview_process.terminate(); preview_process.wait(timeout=15)
            if api_process: api_process.terminate(); api_process.wait(timeout=15)
            if commercial:
                import asyncio
                import httpx
                from sqlalchemy import select
                from f01.db.models import ExecutionJob, IsolatedPreview, ArtifactPreparation
                from f01.db.session import Database
                from f01.execution.docker import DockerSandbox
                disposable = Database(database)
                with disposable.session() as session:
                    names = set(session.scalars(select(IsolatedPreview.container_name))) | set(session.scalars(select(ExecutionJob.container_name))) | set(session.scalars(select(ArtifactPreparation.container_name)))
                async def cleanup():
                    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=api_env['SANDBOX_SOCKET']),base_url='http://docker',trust_env=False,timeout=30) as client:
                        sandbox = DockerSandbox(client,api_env['SANDBOX_IMAGE_ID'])
                        for name in names:
                            if name: await sandbox.remove(name)
                try: asyncio.run(cleanup())
                finally: disposable.close()
raise SystemExit(result.returncode)
