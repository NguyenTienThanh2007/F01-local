"""Controlled HTTP adapter checks. Never count these as live deployment evidence."""
import asyncio
import hashlib
import socket
from typing import Any
from uuid import uuid4
import httpx
import pytest
from f01.db.models import ReleaseArtifact, ReleaseConfiguration
from f01.release.package import package_digest, validate_package
from f01.release.provider import ReleaseProviderError
from f01.release.vercel import VercelProvider
from tests.persistence.test_releases import package


def config() -> ReleaseConfiguration:
    return ReleaseConfiguration(id=uuid4(), project_id=uuid4(), provider_project_id='prj_controlled', provider_team_id=None, public_url='https://public.vercel.app')


def artifact() -> ReleaseArtifact:
    content = package({'test': 'controlled'})
    return ReleaseArtifact(id=uuid4(), project_id=uuid4(), package=content, digest=package_digest(validate_package(content)))


def test_prebuilt_upload_and_stage_have_no_source_build_or_runtime_credentials() -> None:
    target, saved = config(), artifact()
    calls: list[httpx.Request] = []
    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.host == 'api.vercel.com'
        assert request.headers['authorization'] == 'Bearer controlled-release-token'
        if request.url.path == '/v2/files':
            assert request.headers['x-vercel-digest'] == hashlib.sha1(request.content).hexdigest()
            return httpx.Response(200, json={})
        body = __import__('json').loads(request.content)
        assert body['autoAssignCustomDomains'] is False and body['target'] == 'production'
        assert 'env' not in body and 'builds' not in body and 'build' not in body and 'gitSource' not in body
        assert all(x['file'].startswith('.vercel/output/') and 'data' not in x for x in body['files'])
        return httpx.Response(200, json={'id': 'dpl_controlled', 'projectId': target.provider_project_id, 'target': 'production', 'url': 'staged.vercel.app', 'readyState': 'READY', 'meta': body['meta']})
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client, httpx.AsyncClient() as health:
            provider = VercelProvider(client, health, 'controlled-release-token', 'https://factory.example')
            await provider.upload(target, saved)
            value = await provider.stage(target, saved, 'controlled-operation')
            assert value.id == 'dpl_controlled' and value.state == 'READY'
    asyncio.run(run())
    assert len(calls) == len(validate_package(saved.package))+1


@pytest.mark.parametrize('status,code,uncertain,retryable', [(401,'RELEASE_PROVIDER_AUTHENTICATION',False,False),(403,'RELEASE_PROVIDER_AUTHENTICATION',False,False),(429,'RELEASE_PROVIDER_RATE_LIMITED',False,True),(500,'RELEASE_PROVIDER_UNAVAILABLE',True,True)])
def test_provider_failures_are_sanitized_and_uncertain_writes_are_identified(status: int, code: str, uncertain: bool, retryable: bool) -> None:
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json={'message': 'private-provider-log-secret'}))) as client, httpx.AsyncClient() as health:
            provider = VercelProvider(client, health, 'private-credential', 'https://factory.example')
            with pytest.raises(ReleaseProviderError) as result:
                await provider.stage(config(), artifact(), 'controlled')
            assert str(result.value) == code and result.value.uncertain == uncertain and result.value.retryable == retryable
            assert 'secret' not in str(result.value) and 'credential' not in str(result.value)
    asyncio.run(run())


def test_duplicate_resource_correlation_never_selects_an_arbitrary_deployment() -> None:
    async def run() -> None:
        response = {'deployments': [{'uid': 'dpl_first', 'meta': {'f01_operation': 'controlled'}}, {'uid': 'dpl_second', 'meta': {'f01_operation': 'controlled'}}]}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response))) as client, httpx.AsyncClient() as health:
            with pytest.raises(ReleaseProviderError, match='RELEASE_DUPLICATE_PROVIDER_RESOURCE'):
                await VercelProvider(client, health, 'private', 'https://factory.example').find(config(), artifact(), 'controlled')
    asyncio.run(run())


def test_health_is_public_without_tokens_cookies_or_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))])
    saved = artifact()
    files = {f.path: f.data for f in validate_package(saved.package)}
    async def handler(request: httpx.Request) -> httpx.Response:
        assert 'authorization' not in request.headers and 'cookie' not in request.headers
        path = '.vercel/output/static/'+('__f01_release.json' if request.url.path.endswith('.json') else 'index.html')
        return httpx.Response(200, content=files[path])
    async def run() -> None:
        async with httpx.AsyncClient() as client, httpx.AsyncClient(transport=httpx.MockTransport(handler)) as health:
            await VercelProvider(client, health, 'private-provider-token', 'https://factory.example').health('https://public.vercel.app', saved)
    asyncio.run(run())


def test_health_rejects_private_dns_and_foreign_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))])
    async def run() -> None:
        def forbidden(request: httpx.Request) -> httpx.Response:
            raise AssertionError('Private DNS must fail before HTTP dispatch.')
        async with httpx.AsyncClient() as client, httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as health:
            with pytest.raises(ReleaseProviderError, match='RELEASE_URL_INVALID'):
                await VercelProvider(client, health, 'private', 'https://factory.example').health('https://public.vercel.app', artifact())
    asyncio.run(run())
