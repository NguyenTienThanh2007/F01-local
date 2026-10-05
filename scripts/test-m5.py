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
pg_bin = root / '.runtime/postgres/usr/lib/postgresql/16/bin'
if not pg_bin.exists():
    raise SystemExit('This workspace harness needs its provisioned PostgreSQL 16 binaries. Alternatively run test:simulation:e2e with M5_API_URL, M5_TEST_DATABASE_URL and M5_TEST_TOKEN against a disposable migrated f01_test_* database.')
def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); return sock.getsockname()[1]
data = Path(tempfile.mkdtemp(prefix='f01-m5-', dir='/dev/shm')) / 'data'
pg_env = dict(os.environ, LD_LIBRARY_PATH=str(root/'.runtime/postgres/usr/lib/x86_64-linux-gnu'), LD_PRELOAD=str(root/'.runtime/postgres-identity.so'))
subprocess.run([str(pg_bin/'initdb'), '-D', str(data), '-U', 'f01_test', '--auth=trust', '--no-locale', '--encoding=UTF8'], env=pg_env, check=True, stdout=subprocess.DEVNULL)
pg_port, api_port, web_port = port(), port(), port()
token = 'synthetic-m5-browser-token-12345678901234567890'
database = f'postgresql+psycopg://f01_test@127.0.0.1:{pg_port}/f01_test_m5'
api_process = None
try:
    with (root/'.runtime/m5-postgres.log').open('w') as pg_log, (root/'.runtime/m5-api.log').open('w') as api_log:
        pg = subprocess.Popen([str(pg_bin/'postgres'), '-D', str(data), '-h', '127.0.0.1', '-p', str(pg_port), '-c', 'unix_socket_directories=', '-c', 'jit=off', '-c', 'timezone=UTC'], env=pg_env, stdout=pg_log, stderr=pg_log)
        try:
            for _ in range(100):
                try:
                    with psycopg.connect(host='127.0.0.1', port=pg_port, user='f01_test', dbname='postgres', autocommit=True) as connection: connection.execute('CREATE DATABASE f01_test_m5')
                    break
                except psycopg.OperationalError: time.sleep(.1)
            else: raise RuntimeError('PostgreSQL did not start')
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
            pg.terminate(); pg.wait(timeout=15)
finally:
    shutil.rmtree(data.parent)
raise SystemExit(result.returncode)
