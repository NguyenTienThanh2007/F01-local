"""Pre-dispatch cost reservation for explicit live acceptance, never production pricing."""
import fcntl
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

# Standard OpenAI USD per 1M tokens (input, output), checked against the official model
# pages. Any other model fails closed before dispatch rather than guessing a price.
PRICES: dict[str, tuple[float, float]] = {'gpt-4.1-mini': (0.40, 1.60), 'gpt-4.1': (2.00, 8.00)}
# Absolute ceilings no caller can raise, whatever the founder authorizes per run.
MAX_CALLS = 40
MAX_USD = 5.00


def call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES[model]
    return (input_tokens * price_in + output_tokens * price_out) / 1000000


class LiveAcceptanceBudget:
    # UTF-8 request bytes over-reserve input tokens, with protocol overhead.
    call_limit = 4
    dollar_limit = 0.50

    def __init__(self, report: dict[str, object], *, call_limit: int | None = None, dollar_limit: float | None = None,
                 journal: Path | None = None, scenario: str | None = None) -> None:
        if call_limit is not None:
            self.call_limit = call_limit
        if dollar_limit is not None:
            self.dollar_limit = dollar_limit
        assert 0 < self.call_limit <= MAX_CALLS and 0 < self.dollar_limit <= MAX_USD, 'LIVE_ACCEPTANCE_LIMIT_NOT_ALLOWED'
        self.calls = 0
        self.reserved_usd = 0.0
        self.report = report
        self.journal = journal
        self.scenario = scenario
        self._rows: dict[int, int] = {}
        report['provider_call_limit'] = self.call_limit
        report['reserved_standard_rate_limit_usd'] = self.dollar_limit

    def _update(self, change: Callable[[dict[str, Any]], Any]) -> Any:
        # A journal shares one ceiling across scenarios and processes; reservations for
        # unknown outcomes are retained, never reset.
        assert self.journal is not None
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open('a+', encoding='utf-8') as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            file.seek(0)
            state: dict[str, Any] = json.loads(file.read() or json.dumps({'limit_usd': self.dollar_limit, 'call_limit': self.call_limit, 'calls': []}))
            result = change(state)
            file.seek(0)
            file.truncate()
            json.dump(state, file, indent=2)
            file.flush()
            return result

    def stop(self) -> None:
        # Recorded before raising: workers may convert provider exceptions into build codes.
        self.report['budget_stopped'] = True
        raise AssertionError('LIVE_ACCEPTANCE_COST_LIMIT')

    async def reserve(self, request: httpx.Request) -> None:
        body = json.loads(request.content)
        model = body['model']
        assert model in PRICES, 'LIVE_MODEL_PRICE_BOUND_NOT_CONFIGURED'
        output = body['max_output_tokens']
        assert type(output) is int and 0 < output <= 32768, 'LIVE_ACCEPTANCE_OUTPUT_LIMIT'
        upper = call_cost(model, len(request.content) + 4096, output)
        if not (self.calls < self.call_limit and self.reserved_usd + upper <= self.dollar_limit):
            self.stop()
        if self.journal is not None:
            def claim(state: dict[str, Any]) -> int:
                # Settled calls count their observed cost; everything else its full reservation.
                occupied = sum(row.get('estimated_usd', row['reserved_usd']) for row in state['calls'])
                if not (len(state['calls']) < min(state['call_limit'], self.call_limit) and occupied + upper <= min(state['limit_usd'], self.dollar_limit)):
                    self.stop()
                state['calls'].append({'scenario': self.scenario, 'model': model, 'request_bytes': len(request.content),
                    'max_output_tokens': output, 'reserved_usd': round(upper, 8), 'status': 'dispatched'})
                return len(state['calls']) - 1
            self._rows[id(request)] = self._update(claim)
        self.calls += 1
        self.reserved_usd += upper
        self.report['provider_calls'] = self.calls
        self.report['reserved_standard_rate_usd'] = round(self.reserved_usd, 6)

    async def settle(self, response: httpx.Response) -> None:
        """Response hook: record observed usage. Missing usage keeps the full reservation."""
        row = self._rows.pop(id(response.request), None)
        await response.aread()
        try:
            usage = response.json().get('usage') or {}
        except ValueError:
            usage = {}
        model = json.loads(response.request.content)['model']
        tokens_in, tokens_out = usage.get('input_tokens'), usage.get('output_tokens')
        cost: float | None = None
        if response.status_code == 200 and type(tokens_in) is int and type(tokens_out) is int:
            cost = call_cost(model, tokens_in, tokens_out)
        usage_report = self.report.setdefault('usage', {'input_tokens': 0, 'output_tokens': 0, 'estimated_usd': 0.0, 'unsettled_calls': 0})
        assert isinstance(usage_report, dict)
        if cost is not None:
            usage_report['input_tokens'] += tokens_in
            usage_report['output_tokens'] += tokens_out
            usage_report['estimated_usd'] = round(usage_report['estimated_usd'] + cost, 8)
        else:
            usage_report['unsettled_calls'] += 1
        if row is not None:
            def finish(state: dict[str, Any]) -> None:
                state['calls'][row]['status'] = response.status_code
                if cost is not None:
                    state['calls'][row].update(input_tokens=tokens_in, output_tokens=tokens_out, estimated_usd=round(cost, 8))
            self._update(finish)
