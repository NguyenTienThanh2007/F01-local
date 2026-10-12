"""Opt-in disposable live Vercel acceptance. Never prints credentials or raw logs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from test_database import test_database

parser = argparse.ArgumentParser()
parser.add_argument('--socket', required=True)
parser.add_argument('--use-cli-login', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
accepted = json.loads((root/'.runtime/production-acceptance-report.json').read_text())
if any(accepted.get(key) != 'passed' for key in ('docker_containment', 'docker_journey', 'production_packaging')):
    raise SystemExit('PRODUCTION_ACCEPTANCE_REQUIRED')
token = os.environ.get('F01_VERCEL_TOKEN', '')
if not token and args.use_cli_login:
    token = json.loads((Path.home()/'Library/Application Support/com.vercel.cli/auth.json').read_text()).get('token', '')
if not token:
    raise SystemExit('RELEASE_PROVIDER_NOT_CONFIGURED')
with test_database(root) as database:
    env = {**os.environ, 'TEST_DATABASE_URL': database, 'F01_LIVE_VERCEL_ACCEPTANCE': '1', 'F01_VERCEL_TOKEN': token,
        'F01_SANDBOX_IMAGE_ID': accepted['image_id'], 'F01_DOCKER_SOCKET': args.socket}
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/live/test_vercel_acceptance.py', '--junitxml='+str(root/'.runtime/live-acceptance.xml')], cwd=root/'apps/api', env=env)
raise SystemExit(result.returncode)
