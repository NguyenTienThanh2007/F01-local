"""Explicit disposable acceptance worker used to observe a genuine process loss."""
import asyncio
import os
import httpx
from f01.config import get_settings
from f01.db.session import Database
from f01.domain.source import GenerationContext, GenerationResult
from f01.execution.docker import DockerSandbox
from f01.execution.worker import BuildWorker

settings=get_settings()
if settings.app_env!='test' or '/f01_test_' not in settings.database_url or os.environ.get('F01_BUILD_STATE_ACCEPTANCE')!='1':
    raise RuntimeError('Explicit disposable build-state acceptance required.')

class PendingSource:
    async def propose_source(self,context:GenerationContext,maximum_output_tokens:int)->GenerationResult:
        await asyncio.sleep(110)
        raise RuntimeError('Controlled provider remains unconfirmed.')

async def main()->None:
    database=Database(settings.database_url)
    try:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket),base_url='http://docker',trust_env=False,timeout=300) as engine:
            await BuildWorker(database,settings.model_copy(update={'planning_timeout_seconds':120}),DockerSandbox(engine,settings.sandbox_image_id),PendingSource()).run_once()
    finally:database.close()
asyncio.run(main())
