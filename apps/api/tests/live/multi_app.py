"""Shared helpers for opt-in multi-app live acceptance. No model calls happen here."""
import json
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import uvicorn

from f01.config import Settings
from f01.execution.preview_gateway import create_gateway

ROOT = Path(__file__).resolve().parents[4]
CATALOG = ROOT / 'QA/multi-app/scenarios.json'
CHECKER = ROOT / 'apps/web/tests/generated-app-acceptance.mjs'
STAGES = ('planning', 'source_generation', 'docker', 'browser')


def load_scenario(identifier: str) -> dict[str, Any]:
    for scenario in json.loads(CATALOG.read_text())['scenarios']:
        if scenario['id'] == identifier:
            assert isinstance(scenario, dict)
            return scenario
    raise ValueError(f'Unknown acceptance scenario: {identifier}')


def classify_failure(report: dict[str, Any]) -> str | None:
    """Name the first lifecycle stage that did not pass, with its recorded cause."""
    if report.get('budget_stopped'):
        return 'budget_limit'
    for stage in STAGES:
        if report.get(stage) in ('passed', 'not_applicable'):
            continue
        build = report.get('observed_build')
        if stage in ('source_generation', 'docker') and isinstance(build, dict) and build.get('error_code'):
            return f"build:{build['error_code']}"
        result = report.get('browser_result')
        if stage == 'browser' and isinstance(result, dict) and isinstance(result.get('summary'), dict):
            failed = [name for name, row in result['summary'].items() if row.get('passed') != row.get('total')]
            return 'browser:' + ','.join(failed) if failed else 'browser:incomplete'
        return f'{stage}:not_completed'
    return None


def preview_settings(settings: Settings, port: int) -> Settings:
    # Per-project loopback origins give the native app its own localStorage site.
    return settings.model_copy(update={'local_browser_preview_enabled': True, 'preview_origin': f'http://localhost:{port}',
        'factory_origin': 'http://127.0.0.1:3000'})


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        assert isinstance(port, int)
        return port


@contextmanager
def serve_preview_gateway(settings: Settings, port: int) -> Iterator[str]:
    """Runs the real isolated preview gateway on loopback for browser checks."""
    server = uvicorn.Server(uvicorn.Config(create_gateway(settings), host='127.0.0.1', port=port, log_level='warning', lifespan='on'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError('PREVIEW_GATEWAY_UNAVAILABLE')
        time.sleep(0.05)
    try:
        yield f'http://localhost:{port}'
    finally:
        server.should_exit = True
        thread.join(timeout=15)


def run_browser_acceptance(scenario: str, url: str, output: Path, timeout: float = 600) -> dict[str, Any]:
    """Runs the generic Node checker. The capability URL travels only in the child environment."""
    import os
    result = subprocess.run(['node', str(CHECKER)], cwd=ROOT / 'apps/web', capture_output=True, text=True, timeout=timeout,
        env={**os.environ, 'F01_GENERATED_PREVIEW_URL': url, 'F01_ACCEPTANCE_SCENARIO': scenario, 'F01_ACCEPTANCE_OUTPUT': str(output)})
    lines = [line for line in result.stdout.splitlines() if line.startswith('{')]
    summary: dict[str, Any] = json.loads(lines[-1]) if lines else {'passed': False, 'failed': [], 'error': 'CHECKER_DID_NOT_REPORT'}
    summary['exit_code'] = result.returncode
    return summary


def summarize_run(directory: Path, scenarios: list[str], model: str, max_usd: float) -> dict[str, Any]:
    """Aggregates per-scenario reports and the shared usage journal; missing reports stay not_run."""
    rows: list[dict[str, Any]] = []
    for identifier in scenarios:
        path = directory / identifier / 'model-report.json'
        report: dict[str, Any] = json.loads(path.read_text()) if path.exists() else {}
        browser = report.get('browser_result') if isinstance(report.get('browser_result'), dict) else {}
        assert isinstance(browser, dict)
        rows.append({'scenario': identifier, **{stage: report.get(stage, 'not_run') for stage in STAGES},
            'repair_attempts': report.get('repair_attempts'), 'browser_summary': browser.get('summary'),
            'failed_checks': browser.get('failed', []), 'usage': report.get('usage'),
            'failure_category': report.get('failure_category', 'not_run') if report else 'not_run',
            'accepted': bool(report) and report.get('failure_category') is None})
    journal = directory / 'usage.json'
    calls: list[dict[str, Any]] = json.loads(journal.read_text())['calls'] if journal.exists() else []
    settled = [row for row in calls if 'estimated_usd' in row]
    return {'model': model, 'authorized_max_usd': max_usd, 'scenarios': rows,
        'accepted': sum(row['accepted'] for row in rows), 'total': len(rows),
        'provider': {'calls': len(calls), 'settled_calls': len(settled),
            'input_tokens': sum(row['input_tokens'] for row in settled), 'output_tokens': sum(row['output_tokens'] for row in settled),
            'estimated_usd': round(sum(row['estimated_usd'] for row in settled), 6),
            'unsettled_reserved_usd': round(sum(row['reserved_usd'] for row in calls if 'estimated_usd' not in row), 6)},
        'evidence': 'Real provider output, real Docker build and real browser checks; screenshots still require human review.'}


def markdown_summary(summary: dict[str, Any]) -> str:
    lines = [f"# Multi-app live acceptance — {summary['model']}", '',
        f"Accepted {summary['accepted']}/{summary['total']} scenarios. Authorized ceiling ${summary['authorized_max_usd']:.2f}; "
        f"estimated spend ${summary['provider']['estimated_usd']:.4f} over {summary['provider']['calls']} calls "
        f"({summary['provider']['input_tokens']} input + {summary['provider']['output_tokens']} output tokens; "
        f"${summary['provider']['unsettled_reserved_usd']:.4f} reserved for unknown outcomes).", '',
        '| Scenario | Plan | Source | Docker | Browser | Repairs | Functional | Visual | A11y | Runtime | Failure |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in summary['scenarios']:
        counts = row['browser_summary'] or {}
        def cell(name: str) -> str:
            return f"{counts[name]['passed']}/{counts[name]['total']}" if name in counts else '—'
        lines.append(f"| {row['scenario']} | {row['planning']} | {row['source_generation']} | {row['docker']} | {row['browser']} | "
            f"{row['repair_attempts'] if row['repair_attempts'] is not None else '—'} | {cell('functional')} | {cell('visual')} | "
            f"{cell('accessibility')} | {cell('runtime')} | {row['failure_category'] or '—'} |")
    lines += ['', summary['evidence'], '']
    return '\n'.join(lines)
