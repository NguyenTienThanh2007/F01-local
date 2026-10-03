"""Adapter wire/limits tests are controlled transport tests, not containment evidence."""
import asyncio
import json
from uuid import UUID,uuid4
import httpx
import pytest
from f01.execution.docker import DockerSandbox,SandboxError
from f01.domain.source import validate_source_path

IMAGE='sha256:'+'a'*64
NAME='f01-'+('a'*32)+'-1-1'
async def yes()->bool:return True
async def no()->bool:return False

@pytest.mark.parametrize('path',['//evil.test','/\\evil','a','x'*2049])
def test_preview_fetch_rejects_destination_injection(path:str)->None:
    async def run()->None:
        def send(request:httpx.Request)->httpx.Response:raise AssertionError('No transport allowed')
        async with httpx.AsyncClient(transport=httpx.MockTransport(send),base_url='http://docker') as client:
            with pytest.raises(SandboxError):await DockerSandbox(client,IMAGE).fetch(NAME,path,yes)
    asyncio.run(run())


def test_engine_output_bounded_before_parse()->None:
    async def run()->None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,content=b'x'*33)),base_url='http://docker') as client:
            with pytest.raises(SandboxError,match='OUTPUT_LIMIT'):await DockerSandbox(client,IMAGE).request('GET','/probe',limit=32)
    asyncio.run(run())


def test_container_policy_never_inherits_factory_credentials(monkeypatch:pytest.MonkeyPatch)->None:
    monkeypatch.setenv('OPENAI_API_KEY','host-secret')
    async def run()->None:
        def send(request:httpx.Request)->httpx.Response:
            if request.url.path.endswith('/containers/create'):
                body=json.loads(request.content);assert body['User']=='10000:10000';assert body['HostConfig']['NetworkMode']=='none';assert body['HostConfig']['Binds']==[]
                assert 'host-secret' not in request.content.decode();assert all(not v.startswith('OPENAI_API_KEY=') for v in body['Env'])
                assert body['HostConfig']['MemorySwap']==body['HostConfig']['Memory'];assert body['HostConfig']['PidsLimit']<=128
                return httpx.Response(201,json={'Id':'a'*64})
            return httpx.Response(204)
        async with httpx.AsyncClient(transport=httpx.MockTransport(send),base_url='http://docker') as client:await DockerSandbox(client,IMAGE).create(NAME,uuid4(),uuid4(),f'/p/{uuid4()}/'+('b'*43))
    asyncio.run(run())


def test_cancellation_and_timeout_stop_waiting_for_engine()->None:
    async def run()->None:
        async def send(request:httpx.Request)->httpx.Response:
            if request.url.path.endswith('/exec'):return httpx.Response(201,json={'Id':'b'*64})
            await asyncio.sleep(5);return httpx.Response(200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(send),base_url='http://docker') as client:
            sandbox=DockerSandbox(client,IMAGE)
            with pytest.raises(SandboxError,match='CANCELED_OR_LEASE_LOST'):await sandbox.exec(NAME,('/trusted',),1,no)
            with pytest.raises(SandboxError,match='TIMEOUT'):await sandbox.exec(NAME,('/trusted',),0.01,yes)
    asyncio.run(run())


def test_force_cleanup_retries_are_idempotent()->None:
    async def run()->None:
        calls=[]
        def send(request:httpx.Request)->httpx.Response:
            calls.append(str(request.url));assert request.method=='DELETE';return httpx.Response(204 if len(calls)==1 else 404)
        async with httpx.AsyncClient(transport=httpx.MockTransport(send),base_url='http://docker') as client:
            sandbox=DockerSandbox(client,IMAGE);await sandbox.remove(NAME);await sandbox.remove(NAME)
        assert len(calls)==2 and all('force=true' in value and 'v=true' in value for value in calls)
    asyncio.run(run())


def test_helper_output_cannot_inject_source_diagnostics()->None:
    async def run()->None:
        payload=json.dumps({'exit_code':1,'duration_ms':1,'diagnostics':[{'code':'TS2322','path':'app/../../etc/passwd','line':1}]}).encode()
        def send(request:httpx.Request)->httpx.Response:
            if request.url.path.endswith('/exec'):return httpx.Response(201,json={'Id':'b'*64})
            if request.url.path.endswith('/start'):return httpx.Response(200,content=b'\x01\0\0\0'+len(payload).to_bytes(4,'big')+payload)
            return httpx.Response(200,json={'Running':False,'ExitCode':0})
        async with httpx.AsyncClient(transport=httpx.MockTransport(send),base_url='http://docker') as client:
            with pytest.raises(SandboxError,match='EVIDENCE_INVALID'):await DockerSandbox(client,IMAGE).evidence(NAME,'typecheck',('/trusted',),1,yes)
    asyncio.run(run())
