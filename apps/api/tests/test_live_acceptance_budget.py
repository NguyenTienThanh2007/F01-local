"""The live test guard must stop unsafe requests before any transport dispatch."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from tests.live_budget import LiveAcceptanceBudget


def dispatch(payloads: list[dict[str, object]], expected: int, error: str) -> None:
    sent = 0
    report: dict[str, object] = {}
    budget = LiveAcceptanceBudget(report)

    def transport(_: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(200)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport), event_hooks={'request': [budget.reserve]}) as client:
            for payload in payloads:
                await client.post('https://provider.invalid/responses', json=payload)

    with pytest.raises(AssertionError, match=error):
        asyncio.run(run())
    assert sent == budget.calls == expected
    assert budget.reserved_usd <= budget.dollar_limit


def test_live_retry_limit_prevents_fifth_provider_dispatch() -> None:
    dispatch([{'model': 'gpt-4.1-mini', 'max_output_tokens': 8000}] * 5, 4, 'LIVE_ACCEPTANCE_COST_LIMIT')


def test_live_cost_limit_stops_large_request_before_dispatch() -> None:
    dispatch([{'model': 'gpt-4.1-mini', 'max_output_tokens': 8000, 'input': 'x' * 1250000}], 0, 'LIVE_ACCEPTANCE_COST_LIMIT')


@pytest.mark.parametrize('model,output,error', [
    ('unpriced-model', 8000, 'LIVE_MODEL_PRICE_BOUND_NOT_CONFIGURED'),
    ('gpt-4.1-mini', 32769, 'LIVE_ACCEPTANCE_OUTPUT_LIMIT'),
    ('gpt-4.1-mini', True, 'LIVE_ACCEPTANCE_OUTPUT_LIMIT'),
])
def test_live_unknown_model_and_output_limits_never_dispatch(model: str, output: object, error: str) -> None:
    dispatch([{'model': model, 'max_output_tokens': output}], 0, error)


def journal_client(budget: LiveAcceptanceBudget, usage: dict[str, int] | None, sent: list[str]) -> httpx.AsyncClient:
    def transport(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.path)
        return httpx.Response(200, json={'usage': usage} if usage else {})
    return httpx.AsyncClient(transport=httpx.MockTransport(transport),
        event_hooks={'request': [budget.reserve], 'response': [budget.settle]})


def test_stronger_model_is_priced_at_its_own_standard_rate() -> None:
    report: dict[str, object] = {}
    budget = LiveAcceptanceBudget(report)
    async def run() -> None:
        async with journal_client(budget, {'input_tokens': 1000, 'output_tokens': 500}, []) as client:
            await client.post('https://provider.invalid/responses', json={'model': 'gpt-4.1', 'max_output_tokens': 4000})
    asyncio.run(run())
    assert budget.reserved_usd > 4000 * 8.00 / 1000000
    assert report['usage'] == {'input_tokens': 1000, 'output_tokens': 500, 'estimated_usd': 0.006, 'unsettled_calls': 0}


def test_shared_journal_caps_total_spend_across_scenarios_before_dispatch(tmp_path: Path) -> None:
    journal, sent = tmp_path / 'usage.json', list[str]()
    payload = {'model': 'gpt-4.1-mini', 'max_output_tokens': 20000}
    async def run(scenario: str) -> LiveAcceptanceBudget:
        # Each scenario alone fits; together they exceed the shared $0.05 ceiling.
        budget = LiveAcceptanceBudget({}, call_limit=10, dollar_limit=0.05, journal=journal, scenario=scenario)
        async with journal_client(budget, None, sent) as client:
            await client.post('https://provider.invalid/responses', json=payload)
        return budget
    asyncio.run(run('storefront'))
    with pytest.raises(AssertionError, match='LIVE_ACCEPTANCE_COST_LIMIT'):
        asyncio.run(run('social-profile'))
    state = json.loads(journal.read_text())
    assert len(sent) == 1 and [row['scenario'] for row in state['calls']] == ['storefront']
    assert 'estimated_usd' not in state['calls'][0]  # Unknown usage retains the full reservation.


def test_observed_usage_settles_reservation_and_frees_headroom(tmp_path: Path) -> None:
    journal, sent = tmp_path / 'usage.json', list[str]()
    async def run() -> None:
        budget = LiveAcceptanceBudget({}, call_limit=10, dollar_limit=0.05, journal=journal, scenario='analytics-dashboard')
        async with journal_client(budget, {'input_tokens': 2000, 'output_tokens': 1000}, sent) as client:
            await client.post('https://provider.invalid/responses', json={'model': 'gpt-4.1-mini', 'max_output_tokens': 20000})
        second = LiveAcceptanceBudget({}, call_limit=10, dollar_limit=0.05, journal=journal, scenario='storefront')
        async with journal_client(second, {'input_tokens': 2000, 'output_tokens': 1000}, sent) as client:
            await client.post('https://provider.invalid/responses', json={'model': 'gpt-4.1-mini', 'max_output_tokens': 20000})
    asyncio.run(run())
    state = json.loads(journal.read_text())
    assert len(sent) == 2 and [row['estimated_usd'] for row in state['calls']] == [0.0024, 0.0024]


@pytest.mark.parametrize('calls,usd', [(41, 1.0), (4, 5.01), (0, 1.0), (4, 0.0)])
def test_live_limits_cannot_exceed_absolute_ceilings(calls: int, usd: float) -> None:
    with pytest.raises(AssertionError, match='LIVE_ACCEPTANCE_LIMIT_NOT_ALLOWED'):
        LiveAcceptanceBudget({}, call_limit=calls, dollar_limit=usd)
