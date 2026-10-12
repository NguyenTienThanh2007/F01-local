"""The live test guard must stop unsafe requests before any transport dispatch."""
import asyncio
from collections.abc import AsyncIterator
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
    return httpx.AsyncClient(transport=budget.transport(httpx.MockTransport(transport)))


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


class CountingStream(httpx.AsyncByteStream):
    """Lazy provider body: counts how many chunks anything actually pulled."""
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks, self.pulled = chunks, 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            self.pulled += 1
            yield chunk


def test_metering_never_reads_beyond_what_a_bounded_provider_consumes() -> None:
    # Providers stream with a byte cap and abort oversized bodies. Metering must not
    # pre-read the whole body (an unbounded read) before that cap applies.
    stream = CountingStream([b'x' * 1024] * 100)
    budget = LiveAcceptanceBudget({})
    async def run() -> None:
        transport = budget.transport(httpx.MockTransport(lambda request: httpx.Response(200, stream=stream)))
        async with httpx.AsyncClient(transport=transport) as client:
            async with client.stream('POST', 'https://provider.invalid/responses', json={'model': 'gpt-4.1-mini', 'max_output_tokens': 1000}) as response:
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 4096:
                        break
    asyncio.run(run())
    assert stream.pulled <= 5
    assert budget.report['usage'] == {'input_tokens': 0, 'output_tokens': 0, 'estimated_usd': 0.0, 'unsettled_calls': 1}


def test_metering_settles_usage_from_a_fully_streamed_response(tmp_path: Path) -> None:
    body = json.dumps({'usage': {'input_tokens': 2000, 'output_tokens': 1000}}).encode()
    journal = tmp_path / 'usage.json'
    budget = LiveAcceptanceBudget({}, call_limit=5, dollar_limit=0.5, journal=journal, scenario='storefront')
    async def run() -> bytes:
        transport = budget.transport(httpx.MockTransport(lambda request: httpx.Response(200, stream=CountingStream([body[:10], body[10:]]))))
        async with httpx.AsyncClient(transport=transport) as client:
            async with client.stream('POST', 'https://provider.invalid/responses', json={'model': 'gpt-4.1-mini', 'max_output_tokens': 1000}) as response:
                return b''.join([chunk async for chunk in response.aiter_bytes()])
    assert asyncio.run(run()) == body
    assert budget.report['usage'] == {'input_tokens': 2000, 'output_tokens': 1000, 'estimated_usd': 0.0024, 'unsettled_calls': 0}
    assert json.loads(journal.read_text())['calls'][0]['estimated_usd'] == 0.0024


def test_metering_settles_gzip_encoded_usage() -> None:
    import gzip
    body = gzip.compress(json.dumps({'usage': {'input_tokens': 1000, 'output_tokens': 500}}).encode())
    budget = LiveAcceptanceBudget({})
    async def run() -> object:
        transport = budget.transport(httpx.MockTransport(lambda request: httpx.Response(200, headers={'Content-Encoding': 'gzip'}, stream=CountingStream([body]))))
        async with httpx.AsyncClient(transport=transport) as client:
            async with client.stream('POST', 'https://provider.invalid/responses', json={'model': 'gpt-4.1', 'max_output_tokens': 1000}) as response:
                return json.loads(b''.join([chunk async for chunk in response.aiter_bytes()]))
    assert asyncio.run(run()) == {'usage': {'input_tokens': 1000, 'output_tokens': 500}}
    assert budget.report['usage'] == {'input_tokens': 1000, 'output_tokens': 500, 'estimated_usd': 0.006, 'unsettled_calls': 0}


def test_transport_failure_keeps_full_reservation(tmp_path: Path) -> None:
    journal = tmp_path / 'usage.json'
    budget = LiveAcceptanceBudget({}, call_limit=5, dollar_limit=0.5, journal=journal, scenario='social-profile')
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('outcome unknown', request=request)
    async def run() -> None:
        async with httpx.AsyncClient(transport=budget.transport(httpx.MockTransport(broken))) as client:
            await client.post('https://provider.invalid/responses', json={'model': 'gpt-4.1-mini', 'max_output_tokens': 1000})
    with pytest.raises(httpx.ConnectError):
        asyncio.run(run())
    row = json.loads(journal.read_text())['calls'][0]
    assert row['status'] == 0 and 'estimated_usd' not in row and row['reserved_usd'] > 0
