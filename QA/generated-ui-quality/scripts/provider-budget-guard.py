"""Acceptance-only real HTTP cost guard; never produces or replaces model output."""
import fcntl
import json
from pathlib import Path
import httpx

JOURNAL = Path(__file__).with_name('provider-usage.json')
ORIGINAL = httpx.AsyncClient.send


def update(change):
    with JOURNAL.open('a+', encoding='utf-8') as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        file.seek(0)
        report = json.loads(file.read() or '{"limit_usd":0.5,"call_limit":8,"calls":[],"reserved_usd":0}')
        result = change(report)
        file.seek(0);file.truncate();json.dump(report, file, indent=2);file.flush()
        return result


async def guarded(self, request, **kwargs):
    if str(request.url) != 'https://api.openai.com/v1/responses':
        return await ORIGINAL(self, request, **kwargs)
    body = json.loads(request.content)
    if body.get('model') != 'gpt-4.1-mini' or not isinstance(body.get('max_output_tokens'), int):
        raise httpx.RequestError('Acceptance model budget not configured', request=request)
    maximum = body['max_output_tokens']
    if not 0 < maximum <= 12000:
        raise httpx.RequestError('Acceptance output budget exceeded', request=request)
    reservation = ((len(request.content) + 4096) * .40 + maximum * 1.60) / 1000000
    def reserve(report):
        # Settle only completed requests with observed token usage; unknown outcomes
        # retain their full reservation. Historical reservations remain in the ledger.
        occupied = sum(row.get('estimated_uncached_usd', row['reserved_usd']) for row in report['calls'])
        if len(report['calls']) >= report['call_limit'] or occupied + reservation > report['limit_usd']:
            raise httpx.RequestError('Acceptance API budget reached; no request dispatched', request=request)
        number = len(report['calls'])
        report['calls'].append({'model':body['model'],'request_bytes':len(request.content),'max_output_tokens':maximum,'reserved_usd':round(reservation,8),'status':'dispatched'})
        report['reserved_usd'] += reservation
        return number
    number = update(reserve)
    try:
        response = await ORIGINAL(self, request, **kwargs)
        await response.aread()
        value = response.json()
        usage = value.get('usage', {})
        def finish(report):
            row = report['calls'][number]
            row.update(status=response.status_code, input_tokens=usage.get('input_tokens'), output_tokens=usage.get('output_tokens'), cached_input_tokens=usage.get('input_tokens_details', {}).get('cached_tokens'))
            if isinstance(row['input_tokens'], int) and isinstance(row['output_tokens'], int):
                row['estimated_uncached_usd']=(row['input_tokens']*.40+row['output_tokens']*1.60)/1000000
        update(finish)
        return response
    except Exception:
        update(lambda report: report['calls'][number].update(status='outcome-unknown'))
        raise


def install():
    httpx.AsyncClient.send = guarded
