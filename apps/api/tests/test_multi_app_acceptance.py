"""Multi-app acceptance tooling checks. No model calls, Docker or generated applications."""
import json
from pathlib import Path

import pytest

from f01.domain.projects import CreateProject
from tests.live.multi_app import CATALOG, CHECKER, classify_failure, load_scenario, markdown_summary, summarize_run

SCENARIOS = json.loads(CATALOG.read_text())['scenarios']


def contract_names(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [name for item in value for name in contract_names(item)]
    if isinstance(value, dict):
        return [name for item in value.values() for name in contract_names(item)]
    return []


def test_catalog_covers_distinct_app_classes_with_valid_briefs() -> None:
    ids = [scenario['id'] for scenario in SCENARIOS]
    assert ids == ['analytics-dashboard', 'storefront', 'social-profile'] and len(set(ids)) == len(ids)
    checker = CHECKER.read_text()
    for scenario in SCENARIOS:
        CreateProject(title=scenario['title'], brief=scenario['brief'])
        assert f"'{scenario['id']}':" in checker, 'Every catalog scenario needs browser checks'
        assert scenario['primary_selector'].startswith('[aria-label=')
        # Scope stays inside the supported browser-only runtime.
        assert 'No backend, database, external APIs, remote images or fonts' in scenario['brief']


@pytest.mark.parametrize('scenario', SCENARIOS, ids=lambda scenario: scenario['id'])
def test_every_checked_accessible_name_is_stated_in_the_brief(scenario: dict[str, object]) -> None:
    # The checker may only rely on names the model was actually asked to use.
    brief = str(scenario['brief'])
    for name in contract_names(scenario['contract']):
        assert name in brief, name


def test_unknown_scenario_is_rejected() -> None:
    with pytest.raises(ValueError, match='Unknown acceptance scenario'):
        load_scenario('unbounded-full-stack-app')


@pytest.mark.parametrize('report,category', [
    ({'planning': 'passed', 'source_generation': 'passed', 'docker': 'passed', 'browser': 'passed'}, None),
    ({'planning': 'passed', 'source_generation': 'passed', 'docker': 'passed', 'browser': 'not_applicable'}, None),
    ({'planning': 'not_run', 'source_generation': 'not_run', 'docker': 'not_run', 'browser': 'not_run'}, 'planning:not_completed'),
    ({'planning': 'passed', 'source_generation': 'not_run', 'docker': 'not_run', 'browser': 'not_run',
      'observed_build': {'error_code': 'VERIFICATION_FAILED'}}, 'build:VERIFICATION_FAILED'),
    ({'planning': 'passed', 'source_generation': 'not_run', 'budget_stopped': True}, 'budget_limit'),
    ({'planning': 'passed', 'source_generation': 'passed', 'docker': 'passed', 'browser': 'failed',
      'browser_result': {'summary': {'functional': {'passed': 7, 'total': 9}, 'visual': {'passed': 1, 'total': 1},
                                     'accessibility': {'passed': 0, 'total': 1}, 'runtime': {'passed': 2, 'total': 2}}}},
     'browser:functional,accessibility'),
    ({'planning': 'passed', 'source_generation': 'passed', 'docker': 'passed', 'browser': 'failed',
      'browser_result': {'passed': False, 'error': 'CHECKER_DID_NOT_REPORT'}}, 'browser:not_completed'),
])
def test_failure_category_names_first_failed_stage(report: dict[str, object], category: str | None) -> None:
    assert classify_failure(report) == category


def test_run_summary_counts_only_settled_usage_and_keeps_unrun_scenarios_visible(tmp_path: Path) -> None:
    (tmp_path / 'storefront').mkdir()
    (tmp_path / 'storefront/model-report.json').write_text(json.dumps({'planning': 'passed', 'source_generation': 'passed',
        'docker': 'passed', 'browser': 'failed', 'repair_attempts': 1, 'failure_category': 'browser:runtime',
        'browser_result': {'summary': {'functional': {'passed': 9, 'total': 9}, 'runtime': {'passed': 1, 'total': 2}},
                           'failed': ['No failed or external network requests']}}))
    (tmp_path / 'usage.json').write_text(json.dumps({'calls': [
        {'reserved_usd': 0.03, 'input_tokens': 10000, 'output_tokens': 5000, 'estimated_usd': 0.012},
        {'reserved_usd': 0.04}]}))
    summary = summarize_run(tmp_path, ['storefront', 'social-profile'], 'gpt-4.1-mini', 1.0)
    assert summary['accepted'] == 0 and summary['total'] == 2
    assert summary['provider'] == {'calls': 2, 'settled_calls': 1, 'input_tokens': 10000, 'output_tokens': 5000,
                                   'estimated_usd': 0.012, 'unsettled_reserved_usd': 0.04}
    assert [row['failure_category'] for row in summary['scenarios']] == ['browser:runtime', 'not_run']
    table = markdown_summary(summary)
    assert '| storefront | passed | passed | passed | failed | 1 | 9/9 | — | — | 1/2 | browser:runtime |' in table
    assert '| social-profile | not_run | not_run | not_run | not_run | — |' in table
