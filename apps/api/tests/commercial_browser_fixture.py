"""Guarded browser acceptance: real accepted Docker, synthetic OIDC/models/provider.

Controlled provider URLs never prove public deployment. This app cannot run in
production and requires explicit disposable storage and exact-image reports.
"""
import asyncio
import json
from fastapi import Request
from fastapi.responses import JSONResponse
import httpx
from f01.config import get_settings
from f01.execution.docker import DockerSandbox
from f01.execution.worker import BuildWorker
from f01.release.packaging import PackagingWorker
from f01.release.worker import ReleaseWorker
from f01.release.provider import ProvisionedTarget
from f01.release.provisioning import TargetWorker
from tests import phase2a_browser_fixture as fixture
from tests.persistence.test_phase2b import SourceProvider
from tests.persistence.test_releases import ControlledProvider

settings = get_settings()
if settings.app_env != 'test' or '/f01_test_' not in settings.database_url or settings.auth_mode != 'oidc' or not settings.real_execution_enabled or not settings.release_enabled or settings.simulation_runner_enabled:
    raise RuntimeError('Commercial acceptance needs test OIDC, disposable storage, accepted Docker and no simulator.')
app = fixture.app
source_provider = SourceProvider()


class BrowserProvider(ControlledProvider):
    async def find_target(self, name: str) -> ProvisionedTarget | None:
        return getattr(self, 'target_'+name, None)

    async def create_target(self, name: str) -> ProvisionedTarget:
        value = ProvisionedTarget('prj_'+name.removeprefix('f01-'), 'https://'+name+'.vercel.app', None)
        setattr(self, 'target_'+name, value)
        return value


provider = BrowserProvider()


async def model(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    context = json.loads(body['input'])
    change = context['kind'] == 'change'
    content = {'plan': {'project_title': 'Priority change proposal' if change else 'Commercial dashboard plan',
        'product_summary': 'A browser dashboard based on the saved brief.', 'target_users': ['Agency owner'],
        'core_features': [{'name': 'Priority filter' if change else 'Lead overview', 'description': 'Browser workflow.'}],
        'recommended_stack': {'frontend': 'Next.js', 'backend': 'None', 'database': 'None', 'rationale': 'Local browser state.'},
        'implementation_milestones': [{'title': 'Verify dashboard', 'deliverables': ['Review the built workflow']}]},
        'scope': ['Add a priority filter' if change else 'Build a leads overview'], 'assumptions': ['Browser state only'],
        'acceptance_criteria': ['Show the dashboard and filter'], 'out_of_scope': ['Server functions and app database']}
    return httpx.Response(200, json={'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [{'type': 'output_text', 'text': json.dumps(content)}]}]})


fixture.model = model
busy = asyncio.Lock()


@app.post('/test/commercial-step')
async def step(request: Request) -> JSONResponse:
    if request.headers.get('authorization') != 'Bearer '+settings.auth_gateway_token.get_secret_value():
        return JSONResponse({}, status_code=401)
    body = await request.json()
    kind = body.get('kind')
    if kind not in ('build', 'package', 'release', 'target', 'fail-build', 'fail-public', 'reset-failures'):
        return JSONResponse({}, status_code=422)
    async with busy:
        if kind == 'fail-build':
            source_provider.forever = True
        elif kind == 'fail-public':
            provider.bad_public = True
        elif kind == 'reset-failures':
            source_provider.forever = provider.bad_public = False
        else:
            database = request.app.state.database
            if kind in ('build', 'package'):
                async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket), base_url='http://docker', trust_env=False, timeout=300) as engine:
                    worker = BuildWorker(database, settings, DockerSandbox(engine, settings.sandbox_image_id), source_provider) if kind == 'build' else PackagingWorker(database, settings, DockerSandbox(engine, settings.production_image_id))
                    await worker.run_once()
            elif kind == 'target':
                await TargetWorker(database, settings, provider).run_once()
            else:
                # A bounded sequence of explicit worker ticks; production never uses this fixture.
                from sqlalchemy import select
                from f01.application.execution import now
                from f01.db.models import ReleaseOperation
                for _ in range(12):
                    with database.session() as session, session.begin():
                        for op in session.scalars(select(ReleaseOperation).where(ReleaseOperation.state.not_in(('succeeded', 'failed', 'canceled')))):
                            op.next_attempt_at = now()
                    if not await ReleaseWorker(database, settings, provider).run_once():
                        break
    return JSONResponse({'model_transport': 'controlled', 'deployment_provider': 'controlled', 'stage_calls': provider.stage_calls, 'promote_calls': provider.promote_calls})
