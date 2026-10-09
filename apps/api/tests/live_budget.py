"""Pre-dispatch cost reservation for explicit live acceptance, never production pricing."""
import json

import httpx


class LiveAcceptanceBudget:
    # Standard gpt-4.1-mini rates; fail closed if the configured model changes.
    # UTF-8 request bytes over-reserve input tokens, with protocol overhead.
    call_limit = 4
    dollar_limit = 0.50

    def __init__(self, report: dict[str, object]) -> None:
        self.calls = 0
        self.reserved_usd = 0.0
        self.report = report
        report['provider_call_limit'] = self.call_limit
        report['reserved_standard_rate_limit_usd'] = self.dollar_limit

    async def reserve(self, request: httpx.Request) -> None:
        body = json.loads(request.content)
        assert body['model'] == 'gpt-4.1-mini', 'LIVE_MODEL_PRICE_BOUND_NOT_CONFIGURED'
        output = body['max_output_tokens']
        assert type(output) is int and 0 < output <= 32768, 'LIVE_ACCEPTANCE_OUTPUT_LIMIT'
        upper = (len(request.content) + 4096) * 0.40 / 1000000 + output * 1.60 / 1000000
        assert self.calls < self.call_limit and self.reserved_usd + upper <= self.dollar_limit, 'LIVE_ACCEPTANCE_COST_LIMIT'
        self.calls += 1
        self.reserved_usd += upper
        self.report['provider_calls'] = self.calls
        self.report['reserved_standard_rate_usd'] = round(self.reserved_usd, 6)
