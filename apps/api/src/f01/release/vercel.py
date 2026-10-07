"""Vercel staged production Build Output API adapter; no source build or host CLI."""
import asyncio
import hashlib
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlsplit
import httpx
from f01.application.releases import public_url
from f01.db.models import ReleaseArtifact, ReleaseConfiguration
from f01.release.package import validate_package
from f01.release.provider import ReleaseProviderError, StagedDeployment


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'dpl_[A-Za-z0-9]{1,90}', value):
        raise ReleaseProviderError('RELEASE_PROVIDER_INVALID_RESPONSE', uncertain=True)
    return value


class VercelProvider:
    def __init__(self, client: httpx.AsyncClient, health_client: httpx.AsyncClient, token: str, factory_origin: str) -> None:
        if not token:
            raise ReleaseProviderError('RELEASE_PROVIDER_NOT_CONFIGURED')
        self.client, self.health_client, self.token, self.factory_origin = client, health_client, token, factory_origin

    async def request(self, config: ReleaseConfiguration, method: str, path: str, body: object = None, *, content: bytes | None = None, extra_headers: dict[str, str] | None = None, missing_ok: bool = False) -> dict[str, Any]:
        # Fixed provider origin, no caller supplied upstream URLs, no redirects or env proxies.
        headers = {'Authorization': 'Bearer '+self.token, 'Accept': 'application/json', **(extra_headers or {})}
        params = {'teamId': config.provider_team_id} if config.provider_team_id else None
        try:
            async with self.client.stream(method, 'https://api.vercel.com'+path, params=params, headers=headers, json=body if content is None else None, content=content, follow_redirects=False) as response:
                if response.status_code == 404 and missing_ok:
                    return {}
                if not 200 <= response.status_code < 300:
                    code = 'RELEASE_PROVIDER_AUTHENTICATION' if response.status_code in (401, 403) else 'RELEASE_PROVIDER_RATE_LIMITED' if response.status_code == 429 else 'RELEASE_PROVIDER_UNAVAILABLE' if response.status_code >= 500 else 'RELEASE_PROVIDER_REJECTED'
                    raise ReleaseProviderError(code, uncertain=method != 'GET' and response.status_code >= 500, retryable=response.status_code == 429 or response.status_code >= 500)
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(raw)+len(chunk) > 1048576:
                        raise ReleaseProviderError('RELEASE_PROVIDER_INVALID_RESPONSE', uncertain=method != 'GET')
                    raw.extend(chunk)
                result = json.loads(raw) if raw else {}
                if not isinstance(result, dict):
                    raise ValueError()
                return result
        except (httpx.HTTPError, TimeoutError):
            raise ReleaseProviderError('RELEASE_PROVIDER_UNAVAILABLE', uncertain=method != 'GET', retryable=True) from None
        except (ValueError, TypeError):
            raise ReleaseProviderError('RELEASE_PROVIDER_INVALID_RESPONSE', uncertain=method != 'GET') from None

    async def upload(self, config: ReleaseConfiguration, artifact: ReleaseArtifact) -> None:
        for file in validate_package(artifact.package, artifact.digest):
            # Upload is content-addressed and may safely repeat after response loss.
            sha = hashlib.sha1(file.data).hexdigest()
            await self.request(config, 'POST', '/v2/files', content=file.data, extra_headers={'x-vercel-digest': sha, 'Content-Type': 'application/octet-stream'})

    def deployment(self, value: dict[str, Any], config: ReleaseConfiguration, artifact: ReleaseArtifact, operation: str) -> StagedDeployment:
        try:
            meta = value['meta']
            if value.get('projectId') != config.provider_project_id or value.get('target') != 'production' or meta.get('f01_operation') != operation or meta.get('f01_artifact') != artifact.digest:
                raise ValueError()
            state = value.get('readyState') or value.get('state')
            if state not in ('QUEUED', 'INITIALIZING', 'BUILDING', 'READY', 'ERROR', 'CANCELED'):
                raise ValueError()
            url = public_url('https://'+value['url'], self.factory_origin)
            return StagedDeployment(identifier(value.get('id') or value.get('uid')), url, state)
        except (KeyError, ValueError, TypeError, AttributeError):
            raise ReleaseProviderError('RELEASE_PROVIDER_INVALID_RESPONSE', uncertain=True) from None

    async def stage(self, config: ReleaseConfiguration, artifact: ReleaseArtifact, operation: str) -> StagedDeployment:
        files = validate_package(artifact.package, artifact.digest)
        # The .vercel/output tree is the prebuilt handoff recognized by the provider.
        value = await self.request(config, 'POST', '/v13/deployments', {
            'name': 'f01-'+config.project_id.hex, 'project': config.provider_project_id, 'target': 'production', 'version': 2,
            'autoAssignCustomDomains': False, 'source': 'cli',
            'meta': {'f01_operation': operation, 'f01_artifact': artifact.digest},
            'files': [{'file': f.path, 'sha': hashlib.sha1(f.data).hexdigest(), 'size': len(f.data), 'mode': 0o100644} for f in files],
            'projectSettings': {'framework': None, 'buildCommand': None, 'installCommand': None, 'outputDirectory': None},
        })
        return self.deployment(value, config, artifact, operation)

    async def find(self, config: ReleaseConfiguration, artifact: ReleaseArtifact, operation: str) -> StagedDeployment | None:
        # Read bounded provider history. Absence never proves an uncertain write did not happen.
        value = await self.request(config, 'GET', '/v6/deployments?projectId='+config.provider_project_id+'&limit=100')
        entries = value.get('deployments')
        if not isinstance(entries, list) or len(entries) > 100:
            raise ReleaseProviderError('RELEASE_PROVIDER_INVALID_RESPONSE')
        matches = [x for x in entries if isinstance(x, dict) and isinstance(x.get('meta'), dict) and x['meta'].get('f01_operation') == operation]
        if len(matches) > 1:
            raise ReleaseProviderError('RELEASE_DUPLICATE_PROVIDER_RESOURCE', uncertain=True)
        if not matches:
            return None
        return await self.observe(config, artifact, operation, identifier(matches[0].get('uid') or matches[0].get('id')))

    async def observe(self, config: ReleaseConfiguration, artifact: ReleaseArtifact, operation: str, deployment: str) -> StagedDeployment:
        value = await self.request(config, 'GET', '/v13/deployments/'+identifier(deployment))
        return self.deployment(value, config, artifact, operation)

    async def routing(self, config: ReleaseConfiguration) -> str | None:
        hostname = urlsplit(public_url(config.public_url, self.factory_origin)).hostname
        value = await self.request(config, 'GET', '/v4/aliases/'+str(hostname), missing_ok=True)
        if not value:
            return None
        if value.get('projectId') != config.provider_project_id:
            raise ReleaseProviderError('RELEASE_ROUTING_CONFLICT', uncertain=True)
        deployment = value.get('deployment')
        if not isinstance(deployment, dict):
            raise ReleaseProviderError('RELEASE_PROVIDER_INVALID_RESPONSE')
        return identifier(deployment.get('id'))

    async def promote(self, config: ReleaseConfiguration, deployment: str) -> None:
        await self.request(config, 'POST', '/v10/projects/'+config.provider_project_id+'/promote/'+identifier(deployment), {})

    async def cancel(self, config: ReleaseConfiguration, deployment: str) -> None:
        await self.request(config, 'PATCH', '/v12/deployments/'+identifier(deployment)+'/cancel', {})

    async def clear(self, config: ReleaseConfiguration, deployment: str) -> None:
        # First-release compensation can remove only its observed alias, never another deployment's routing.
        if await self.routing(config) != deployment:
            raise ReleaseProviderError('RELEASE_ROUTING_CONFLICT', uncertain=True)
        hostname = urlsplit(public_url(config.public_url, self.factory_origin)).hostname
        alias = await self.request(config, 'GET', '/v4/aliases/'+str(hostname))
        uid = alias.get('uid')
        if not isinstance(uid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', uid):
            raise ReleaseProviderError('RELEASE_PROVIDER_INVALID_RESPONSE')
        await self.request(config, 'DELETE', '/v2/aliases/'+uid)

    async def health(self, url: str, artifact: ReleaseArtifact) -> None:
        origin = public_url(url, self.factory_origin)
        host = urlsplit(origin).hostname
        assert host is not None
        # Allow only provider HTTPS names resolving solely to public addresses.
        try:
            addresses = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
                raise ReleaseProviderError('RELEASE_URL_INVALID')
            files = {f.path: f for f in validate_package(artifact.package, artifact.digest)}
            for suffix, expected in (('/__f01_release.json', files['.vercel/output/static/__f01_release.json'].data), ('/', files['.vercel/output/static/index.html'].data)):
                async with self.health_client.stream('GET', origin+suffix, headers={'Cache-Control': 'no-cache'}, follow_redirects=False) as response:
                    if response.status_code != 200 or response.headers.get('set-cookie'):
                        raise ReleaseProviderError('RELEASE_HEALTH_FAILED')
                    result = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(result)+len(chunk) > 2097152:
                            raise ReleaseProviderError('RELEASE_HEALTH_FAILED')
                        result.extend(chunk)
                    if bytes(result) != expected:
                        raise ReleaseProviderError('RELEASE_HEALTH_FAILED')
        except (httpx.HTTPError, OSError, TimeoutError):
            raise ReleaseProviderError('RELEASE_HEALTH_UNAVAILABLE', retryable=True) from None
