"""Opt-in multi-app real-model acceptance: real OpenAI, real Docker, real browser checks.

Spends money only within an explicit --max-usd ceiling shared by every scenario. Each
scenario uses a fresh disposable PostgreSQL database and removes its containers.
"""
import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values
from test_database import test_database

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'apps/api'))
from tests.live.multi_app import CATALOG, markdown_summary, summarize_run  # noqa: E402
from tests.live_budget import MAX_CALLS, MAX_USD, PRICES  # noqa: E402

ids = [item['id'] for item in json.loads(CATALOG.read_text())['scenarios']]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--scenario', action='append', choices=ids, help='Repeatable; defaults to every catalog scenario.')
parser.add_argument('--model', choices=sorted(PRICES), default='gpt-4.1-mini')
parser.add_argument('--max-usd', type=float, required=True, help=f'Authorized total ceiling for this run (at most {MAX_USD:.2f}).')
parser.add_argument('--max-calls', type=int, help=f'Total provider calls (default 8 per scenario, at most {MAX_CALLS}).')
parser.add_argument('--source-output-tokens', type=int, default=12000)
parser.add_argument('--socket', default=os.environ.get('F01_DOCKER_SOCKET') or str(Path.home() / '.docker/run/docker.sock'))
parser.add_argument('--dry-run', action='store_true', help='Check prerequisites and print the plan without any provider call.')
args = parser.parse_args()
scenarios = args.scenario or ids
calls = args.max_calls or min(MAX_CALLS, 8 * len(scenarios))
if not 0 < args.max_usd <= MAX_USD or not 0 < calls <= MAX_CALLS or not 1000 <= args.source_output_tokens <= 16000:
    parser.error('Limits exceed the acceptance ceilings.')

values = {**dotenv_values(root / '.env'), **dotenv_values(root / 'apps/api/.env'), **os.environ}
blockers = []
if not values.get('OPENAI_API_KEY'):
    blockers.append('PROVIDER_NOT_CONFIGURED: OPENAI_API_KEY is not set in the environment or apps/api/.env')
image = None
for name in ('production-acceptance-report.json', 'phase2b-acceptance-report.json'):
    path = root / '.runtime' / name
    if path.exists():
        accepted = json.loads(path.read_text())
        if accepted.get('docker_containment') == accepted.get('docker_journey') == 'passed':
            image = accepted['image_id']
            break
if not image:
    blockers.append('DOCKER_ACCEPTANCE_REQUIRED: run exact-image Docker acceptance first (scripts/test-backend.py --docker ...)')
if not Path(args.socket).is_socket():
    blockers.append(f'DOCKER_SOCKET_UNAVAILABLE: {args.socket}')
plan = {'scenarios': scenarios, 'model': args.model, 'max_usd': args.max_usd, 'max_calls': calls, 'blockers': blockers}
print(json.dumps(plan, indent=2))
if blockers or args.dry_run:
    raise SystemExit(2 if blockers else 0)

directory = root / '.runtime/multi-app' / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{args.model}"
directory.mkdir(parents=True)
for identifier in scenarios:
    with test_database(root) as database:
        env = {**os.environ, 'TEST_DATABASE_URL': database, 'F01_LIVE_MODEL_ACCEPTANCE': '1', 'OPENAI_API_KEY': str(values['OPENAI_API_KEY']),
            'OPENAI_MODEL': args.model, 'F01_SANDBOX_IMAGE_ID': image, 'F01_DOCKER_SOCKET': args.socket,
            'F01_LIVE_ACCEPTANCE_SCENARIO': identifier, 'F01_LIVE_REPORT_PATH': str(directory / identifier / 'model-report.json'),
            'F01_LIVE_USAGE_JOURNAL': str(directory / 'usage.json'), 'F01_LIVE_MAX_USD': str(args.max_usd),
            'F01_LIVE_CALL_LIMIT': str(calls), 'F01_LIVE_SOURCE_OUTPUT_TOKENS': str(args.source_output_tokens)}
        subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/live/test_model_acceptance.py',
            '--junitxml=' + str(directory / identifier / 'pytest.xml')], cwd=root / 'apps/api', env=env)
    report = directory / identifier / 'model-report.json'
    if report.exists() and json.loads(report.read_text()).get('budget_stopped'):
        print('Authorized budget reached; remaining scenarios are not run.')
        break
summary = summarize_run(directory, scenarios, args.model, args.max_usd)
(directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
(directory / 'summary.md').write_text(markdown_summary(summary))
print(markdown_summary(summary))
print(f'Evidence: {directory.relative_to(root)}')
raise SystemExit(0 if summary['accepted'] == summary['total'] else 1)
