"""The live test guard must stop unsafe requests before any transport dispatch."""
import asyncio

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
