"""Run persisted browser acceptance with disposable PostgreSQL and controlled providers."""
from pathlib import Path
import os, subprocess, time, tempfile, shutil, socket, sys
import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
root = Path(__file__).resolve().parents[1]
if sys.argv[1:] not in ([], ['--phase1'], ['--phase2a'], ['--ux0']):
    raise SystemExit('Usage: test-m5.py [--phase1|--phase2a|--ux0]')
ux0 = sys.argv[1:] == ['--ux0']
phase2 = ux0 or sys.argv[1:] == ['--phase2a']
suite = 'test:ux0:e2e' if ux0 else 'test:phase2a:e2e' if phase2 else 'test:phase1:e2e' if sys.argv[1:] else 'test:simulation:e2e'
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
            api_env = dict(os.environ, SIMULATION_RUNNER_ENABLED='false' if ux0 else 'true', SIMULATION_CHANGE_SCENARIO='terminal-failure', SIMULATION_TICK_MS='800', APP_ENV='test', AUTH_MODE='development', EXECUTION_MODE='simulated', DATABASE_URL=database, DEV_API_TOKEN=token, DEV_AUTH_SUBJECT='m5-browser-owner', OPENAI_API_KEY='')
            if phase2:
                from cryptography.fernet import Fernet
                api_env.update(AUTH_MODE='oidc', AUTH_GATEWAY_TOKEN='synthetic-phase2a-gateway-12345678901234567890', SESSION_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                    OIDC_ISSUER=f'http://127.0.0.1:{api_port}/oidc', OIDC_AUTHORIZATION_URL=f'http://127.0.0.1:{api_port}/oidc/authorize',
                    OIDC_TOKEN_URL=f'http://127.0.0.1:{api_port}/oidc/token', OIDC_JWKS_URL=f'http://127.0.0.1:{api_port}/oidc/jwks',
                    OIDC_CLIENT_ID='fixture-client', OIDC_CLIENT_SECRET='synthetic-fixture-client-secret', OIDC_API_AUDIENCE='fixture-api',
                    OIDC_REDIRECT_URI=f'http://127.0.0.1:{web_port}/api/auth/callback', OPENAI_API_KEY='synthetic-phase2a-provider-key',
                    PLANNING_TIMEOUT_SECONDS='10', PLANNING_REQUESTS_PER_MINUTE='20')
            api_process = subprocess.Popen([str(root/'apps/api/.venv/bin/python'), '-m', 'uvicorn', *(['ux0_browser_fixture:app' if ux0 else 'phase2a_browser_fixture:app','--app-dir',str(root/'apps/api/tests')] if phase2 else ['f01.main:app']), '--host', '127.0.0.1', '--port', str(api_port)], cwd=root/'apps/api', env=api_env, stdout=api_log, stderr=api_log)
            import urllib.request
            for _ in range(100):
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{api_port}/v1/health/live').close(); break
                except OSError: time.sleep(.1)
            else: raise RuntimeError('API did not start')
            test_env = dict(os.environ, M5_API_URL=f'http://127.0.0.1:{api_port}', M5_TEST_DATABASE_URL=database, M5_TEST_TOKEN=token)
            if phase2: test_env.update(P2A_WEB_PORT=str(web_port), AUTH_GATEWAY_TOKEN=api_env['AUTH_GATEWAY_TOKEN'], AUTH_MODE='oidc')
            browser = root/'.runtime/browser/extracted/chromium'
            if browser.exists(): test_env['PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH'] = str(browser)
            axe = root/'.runtime/a11y/node_modules/axe-core/axe.min.js'
            if axe.exists(): test_env['M5_AXE_SCRIPT'] = str(axe)
            result = subprocess.run(['pnpm', '--filter', '@f01/web', suite], cwd=root, env=test_env)
        finally:
            if api_process: api_process.terminate(); api_process.wait(timeout=15)
raise SystemExit(result.returncode)
