"""Run regression or Docker acceptance with a fresh disposable test database."""
from pathlib import Path
import os
import subprocess
import sys
from test_database import test_database

root = Path(__file__).resolve().parents[1]
with test_database(root) as url:
    args = sys.argv[1:]
    if args[:1] == ['--docker']:
        command = [sys.executable, str(root / 'scripts/run-phase2b-acceptance.py'), '--database-url', url, *args[1:]]
        cwd = root
    else:
        command = [sys.executable, '-m', 'pytest', *(args or ['-q'])]
        cwd = root / 'apps/api'
    result = subprocess.run(command, cwd=cwd, env={**os.environ, 'TEST_DATABASE_URL': url})
raise SystemExit(result.returncode)
