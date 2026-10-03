"""Real containers + real OIDC validation, controlled OpenAI responses. No paid model call."""
import asyncio
import json
import os
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select
from f01.application import planning
from f01.application.identity import start_login,finish_login
from f01.config import Settings
from f01.db.models import ExecutionJob, IsolatedPreview
from f01.db.session import Database
from f01.domain.context_planning import ContextPlan, PlanInput, PlanningResult
from f01.domain.execution import StartBuild
from f01.domain.planning import ProjectPlan
from f01.domain.source import GenerationContext
from f01.execution.docker import DockerSandbox, SandboxError
from f01.execution.preview_gateway import create_gateway
from f01.execution.sandbox import SandboxLimits
from f01.execution.worker import BuildWorker
from f01.main import create_app
from f01.providers.openai_source import OpenAISourceGenerationProvider
from tests.persistence.test_phase2a import oidc_settings,token,verifier
from tests.persistence.test_phase2b import SourceProvider,review_plan


def configured(settings:Settings)->Settings:
    return oidc_settings(settings).model_copy(update={'real_execution_enabled':True,'execution_mode':'real','sandbox_image_id':os.environ['F01_SANDBOX_IMAGE_ID'],'sandbox_socket':os.environ.get('F01_DOCKER_SOCKET','/var/run/docker.sock'),'planning_timeout_seconds':30.0,'planning_daily_token_budget':10000000,'planning_requests_per_minute':30,'factory_origin':'http://localhost:3000','preview_origin':'http://127.0.0.1:3031','session_idle_seconds':3600})

async def alive()->bool:return True


def test_docker_containment_and_resource_enforcement(project_settings:Settings)->None:
    settings=configured(project_settings)
    async def journey()->None:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket),base_url='http://docker',trust_env=False,timeout=180) as engine:
            limits=SandboxLimits(memory_bytes=268435456,cpus=1,processes=128,workspace_bytes=16777216,temporary_bytes=16777216)
            sandbox=DockerSandbox(engine,settings.sandbox_image_id,600,limits)
            await sandbox.ready()
            name=sandbox.name(uuid4(),1,1)
            try:
                await sandbox.create(name,uuid4(),uuid4(),f'/p/{uuid4()}/'+('a'*43))
                report=json.loads(await sandbox.exec(name,('/usr/local/bin/node','/opt/f01/policy-probe.mjs'),15,alive))
                assert report['uid']==report['gid']==10000
                assert int(report['capabilities'],16)==0 and report['noNewPrivileges']=='1'
                assert report['readonly'] and report['socketAbsent'] and set(report['interfaces'])<={'lo'}
                assert report['seccomp']=='2' and report['metadataBlocked']
                assert report['memory']=='268435456' and report['pids']=='128'
                quota,period=map(int,report['cpu'].split());assert quota/period==1
                assert report['workspaceBytes']==16777216
                assert not set(report['envNames'])&{'OPENAI_API_KEY','DATABASE_URL','DEV_API_TOKEN','AUTH_GATEWAY_TOKEN'}
                disk=json.loads(await sandbox.exec(name,('/usr/local/bin/node','/opt/f01/resource-probe.mjs','disk'),15,alive));assert disk['full']
                pids=json.loads(await sandbox.exec(name,('/usr/local/bin/node','/opt/f01/resource-probe.mjs','pids'),15,alive));assert int(pids['events'].split()[1])>0
                cpu=json.loads(await sandbox.exec(name,('/usr/local/bin/node','/opt/f01/resource-probe.mjs','cpu'),15,alive));stats=dict(line.split() for line in cpu['stat'].splitlines());assert int(stats['nr_throttled'])>0
                with pytest.raises(SandboxError):await sandbox.exec(name,('/usr/local/bin/node','/opt/f01/resource-probe.mjs','memory'),30,alive)
                report=json.loads(await sandbox.exec(name,('/usr/local/bin/node','/opt/f01/policy-probe.mjs'),15,alive))
                events=dict(line.split() for line in report['memoryEvents'].splitlines());assert int(events['oom_kill'])>0
                with pytest.raises(SandboxError,match='SANDBOX_TIMEOUT'):await sandbox.exec(name,('/bin/sleep','5'),0.1,alive)
                async def canceled()->bool:return False
                with pytest.raises(SandboxError,match='BUILD_CANCELED_OR_LEASE_LOST'):await sandbox.exec(name,('/bin/sleep','5'),10,canceled)
            finally:await sandbox.remove(name)
            assert await sandbox.request('GET',f'/containers/{name}/json',missing_ok=True)==b''
    asyncio.run(journey())
    os.environ["F01_CONTAINMENT_VERIFIED_ID"]=settings.sandbox_image_id


def test_docker_signed_in_build_repair_preview_change_and_failed_update(database:Database,project_settings:Settings,project_plan:ProjectPlan,monkeypatch:pytest.MonkeyPatch)->None:
    settings=configured(project_settings)
    assert os.environ.get("F01_CONTAINMENT_VERIFIED_ID")==settings.sandbox_image_id, "Run and pass containment before generated code execution."
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    check=verifier(settings,key)
    flow=start_login(database,settings);query=parse_qs(urlsplit(flow['authorization_url']).query)
    access=token(settings,key,exp=__import__('time').time()+3600)
    identity=token(settings,key,aud=settings.oidc_client_id,nonce=query['nonce'][0])
    async def exchange(request:httpx.Request)->httpx.Response:
        assert parse_qs(request.content.decode())['code_verifier']
        return httpx.Response(200,json={'access_token':access,'id_token':identity,'token_type':'Bearer'})
    original=httpx.AsyncClient
    with monkeypatch.context() as scoped:
        scoped.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(exchange),**kwargs))
        session=asyncio.run(finish_login(database,settings,check,query['state'][0],flow['binding'],'controlled-code'))
    app=create_app(settings)
    controlled=SourceProvider(broken=True)
    async def model(request:httpx.Request)->httpx.Response:
        body=json.loads(request.content);assert body['store'] is False and 'tools' not in body
        context=GenerationContext.model_validate_json(body['input'])
        result=await controlled.propose_source(context,body['max_output_tokens'])
        return httpx.Response(200,json={'status':'completed','output':[{'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':result.proposal.model_dump_json()}]}],'usage':{'input_tokens':100,'output_tokens':200}})
    async def work()->None:
        async with original(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket),base_url='http://docker',trust_env=False,timeout=180) as engine,original(transport=httpx.MockTransport(model),trust_env=False) as provider_http:
            sandbox=DockerSandbox(engine,settings.sandbox_image_id)
            provider=OpenAISourceGenerationProvider(client=provider_http,api_key=settings.openai_api_key,model=settings.openai_model,timeout_seconds=30)
            assert await BuildWorker(database,settings,sandbox,provider).run_once()
    with TestClient(app) as client:
        app.state.oidc_verifier=check
        client.headers.update({'Authorization':'Bearer '+access,'X-F01-Session':session['session'],'X-F01-CSRF':session['csrf']})
        assert client.get('/v1/session').json()['principal']['identity_mode']=='oidc'
        created=client.post('/v1/projects',json={'title':'Docker acceptance','brief':'Build a browser-only leads dashboard with a summary.'},headers={'Idempotency-Key':str(uuid4())})
        assert created.status_code==201
        data=created.json();pid=UUID(data['project']['id']);owner=UUID(data['project']['owner_user_id'])
        plan=review_plan(database,settings,project_plan,owner,pid,UUID(data['request_id']),'initial')
        queued=client.post(f'/v1/projects/{pid}/builds',json=plan.model_dump(mode='json'),headers={'Idempotency-Key':'acceptance-initial'});assert queued.status_code==202
        asyncio.run(work())
        first=client.get(f'/v1/projects/{pid}/workspace').json()
        assert first['current_version']['mode']=='real'
        run=client.get(f'/v1/projects/{pid}/builds/{queued.json()["id"]}').json()
        assert run['run']['status']=='succeeded' and run['repair_attempts']==1
        assert any(e['phase']=='typecheck' and e['exit_code']!=0 for e in run['evidence'])
        def preview_html(saved:dict[str,object])->str:
            version=saved['current_version'];assert isinstance(version,dict)
            descriptor=version['preview_descriptor'];assert isinstance(descriptor,dict)
            url=str(descriptor['url'])
            with TestClient(create_gateway(settings),base_url=settings.preview_origin) as gateway:
                response=gateway.get(url,headers={'Cookie':'factory_session=must-never-forward','Authorization':'Bearer must-never-forward'})
                assert response.status_code==200 and 'Verified dashboard' in response.text
                assert response.headers.get('set-cookie') is None
                csp=response.headers['content-security-policy'];assert 'sandbox allow-scripts;' in csp and 'allow-same-origin' not in csp and "worker-src 'none'" in csp
                assert gateway.get(url.replace(url.split('/')[-2],'x'*43)).status_code==404
                return str(response.text)
        preview_html(first)
        assert client.get(f'/v1/projects/{pid}/workspace').json()['current_version']==first['current_version']
        changed=client.post(f'/v1/projects/{pid}/requests',json={'text':'Add a priority filter to the existing leads dashboard.','base_brain_revision_id':first['project']['current_brain_revision_id'],'base_version_id':first['project']['current_version_id']},headers={'Idempotency-Key':'acceptance-change'});assert changed.status_code==201
        plan=review_plan(database,settings,project_plan,owner,pid,UUID(changed.json()['id']),'change')
        response=client.post(f'/v1/projects/{pid}/builds',json=plan.model_dump(mode='json'),headers={'Idempotency-Key':'acceptance-change-build'});assert response.status_code==202
        controlled.broken=False;asyncio.run(work())
        second=client.get(f'/v1/projects/{pid}/workspace').json();assert second['current_version']['id']!=first['current_version']['id'];preview_html(second)
        old=client.get(f'/v1/projects/{pid}/versions/{first["current_version"]["id"]}/source').json()
        new=client.get(f'/v1/projects/{pid}/versions/{second["current_version"]["id"]}/source').json()
        assert new['parent_digest']==old['digest']
        assert next(f for f in old['files'] if f['path']=='app/layout.tsx')==next(f for f in new['files'] if f['path']=='app/layout.tsx')
        failed=client.post(f'/v1/projects/{pid}/requests',json={'text':'Attempt another update to the existing dashboard layout.','base_brain_revision_id':second['project']['current_brain_revision_id'],'base_version_id':second['project']['current_version_id']},headers={'Idempotency-Key':'acceptance-fail'});assert failed.status_code==201
        plan=review_plan(database,settings,project_plan,owner,pid,UUID(failed.json()['id']),'change')
        response=client.post(f'/v1/projects/{pid}/builds',json=plan.model_dump(mode='json'),headers={'Idempotency-Key':'acceptance-failed-build'});assert response.status_code==202
        controlled.forever=True;asyncio.run(work())
        final=client.get(f'/v1/projects/{pid}/workspace').json();assert final['current_version']==second['current_version'] and final['current_brain']==second['current_brain'];preview_html(final)
        # Remove retained previews; the test never leaves generated runtimes behind.
    async def cleanup()->None:
        with database.session() as session:
            previews=session.scalars(select(IsolatedPreview)).all()
        async with original(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket),base_url='http://docker',trust_env=False,timeout=30) as engine:
            sandbox=DockerSandbox(engine,settings.sandbox_image_id)
            for item in previews:await sandbox.remove(item.container_name)
    asyncio.run(cleanup())
