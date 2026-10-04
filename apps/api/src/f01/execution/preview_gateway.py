"""Separate cookie host and process; private Docker exec forwards HTTP through network-none."""
import asyncio
import secrets
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from uuid import UUID
from fastapi import FastAPI, Request
from fastapi.responses import Response
import httpx
from f01.application.identity import digest
from f01.application.execution import now
from f01.config import Settings, get_settings
from f01.db.models import IsolatedPreview
from f01.db.session import Database
from f01.execution.docker import DockerSandbox, SandboxError


def create_gateway(settings:Settings|None=None)->FastAPI:
    @asynccontextmanager
    async def lifespan(app:FastAPI)->AsyncIterator[None]:
        configured=settings or get_settings()
        app.state.settings=configured
        app.state.database=Database(configured.database_url)
        app.state.capacity=asyncio.Semaphore(8)
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=configured.sandbox_socket),base_url='http://docker',trust_env=False,timeout=12) as engine:
            app.state.sandbox=DockerSandbox(engine,configured.sandbox_image_id)
            try:yield
            finally:app.state.database.close()
    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    @app.get('/p/{preview_id}/{capability}/{path:path}')
    async def preview(preview_id:UUID,capability:str,path:str,request:Request)->Response:
        configured:Settings=request.app.state.settings
        if not configured.real_execution_enabled or len(capability)!=43:return Response(status_code=404)
        # Strict host binding; cookies/auth headers are ignored and never forwarded.
        from urllib.parse import urlsplit
        if request.headers.get('host')!=urlsplit(configured.preview_origin).netloc:return Response(status_code=404)
        database:Database=request.app.state.database
        with database.session() as session:
            row=session.get(IsolatedPreview,preview_id)
            if row is None or row.state!='ready' or row.expires_at<=now() or not secrets.compare_digest(row.capability_hash,digest(capability)):return Response(status_code=404)
            name=row.container_name
        async def alive()->bool:
            with database.session() as session:
                saved=session.get(IsolatedPreview,preview_id)
                return saved is not None and saved.state=='ready' and saved.expires_at>now()
        base=f'/p/{preview_id}/{capability}'
        target=f'{base}/{path}' if path else base
        if request.url.query:target+='?'+request.url.query
        try:
            async with request.app.state.capacity:
                status,kind,body=await request.app.state.sandbox.fetch(name,target,alive)
        except SandboxError:return Response(status_code=503)
        # No upstream headers, cookies, redirects, service workers or arbitrary destinations.
        if status not in (200,404):return Response(status_code=502)
        origin=configured.preview_origin
        headers={'Content-Type':kind,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Access-Control-Allow-Origin':'*',
            'Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
            'Content-Security-Policy':f"sandbox allow-scripts; default-src 'none'; script-src {origin} 'unsafe-inline'; style-src {origin} 'unsafe-inline'; img-src {origin} data:; font-src {origin}; connect-src {origin}; frame-src 'none'; worker-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors {configured.factory_origin}; object-src 'none'"}
        return Response(body,status_code=status,headers=headers)
    return app

app=create_gateway()
