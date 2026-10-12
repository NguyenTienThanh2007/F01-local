"""Opt-in bounded live planning/source acceptance; disposable data and real Docker."""
import json
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values
from test_database import test_database

root = Path(__file__).resolve().parents[1]
accepted = json.loads((root / '.runtime/production-acceptance-report.json').read_text())
values = {**dotenv_values(root / '.env'), **dotenv_values(root / 'apps/api/.env'), **os.environ}
key = values.get('OPENAI_API_KEY')
if not key:
    raise SystemExit('PROVIDER_NOT_CONFIGURED')
with test_database(root) as database:
    env = {**os.environ, 'TEST_DATABASE_URL': database, 'F01_LIVE_MODEL_ACCEPTANCE': '1',
        'OPENAI_API_KEY': key, 'OPENAI_MODEL': values.get('OPENAI_MODEL') or 'gpt-4.1-mini',
        'F01_SANDBOX_IMAGE_ID': accepted['image_id'],
        'F01_DOCKER_SOCKET': os.environ.get('F01_DOCKER_SOCKET') or str(Path.home()/'.docker/run/docker.sock')}
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/live/test_model_acceptance.py',
        '--junitxml='+str(root/'.runtime/live-model.xml')], cwd=root/'apps/api', env=env)
raise SystemExit(result.returncode)
