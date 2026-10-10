"""One bounded live model plan and source build. Never replaces controlled regressions."""
import asyncio
import json
import os
import sys
import threading
from types import FrameType
from typing import TYPE_CHECKING
from pathlib import Path
from uuid import UUID
import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from f01.application import planning
from f01.application.identity import digest
from f01.config import Settings
from f01.db import models as db
from f01.db.session import Database
from f01.domain.context_planning import PlanInput
from f01.execution.docker import DockerSandbox
from f01.execution.worker import BuildWorker
from f01.main import create_app
from f01.providers.factory import source_provider
from f01.providers.openai import OpenAIPlanningProvider
from tests.live_budget import LiveAcceptanceBudget
if TYPE_CHECKING:
    from _typeshed import TraceFunction


def test_live_context_plan_and_verified_source(database: Database, project_settings: Settings) -> None:
    root=Path(__file__).resolve().parents[4]
    report: dict[str, object]={'planning':'not_run','source_generation':'not_run','docker':'not_run',
        'provider':'openai','model':os.environ['OPENAI_MODEL'],'identity':'development test principal','scenario':'agency-task-tracker' if os.environ.get('F01_LIVE_ACCEPTANCE_BRIEF') else 'checklist'}
    report_path=root/'.runtime/live-model-report.json'
    budget=LiveAcceptanceBudget(report)
    image=os.environ['F01_SANDBOX_IMAGE_ID']
    settings=project_settings.model_copy(update={'execution_mode':'real','real_execution_enabled':True,
        'sandbox_image_id':image,'sandbox_socket':os.environ['F01_DOCKER_SOCKET'],
        'simulation_runner_enabled':False,'openai_api_key':SecretStr(os.environ['OPENAI_API_KEY']),
        'openai_model':os.environ['OPENAI_MODEL'],'planning_timeout_seconds':120,
        'repair_attempts':2,'planning_daily_token_budget':500000})
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    try:
        with TestClient(create_app(settings)) as client:
            client.headers['Authorization']='Bearer '+settings.dev_api_token.get_secret_value()
            saved=client.post('/v1/projects',json={'title':'Disposable live model acceptance',
                'brief':os.environ.get('F01_LIVE_ACCEPTANCE_BRIEF') or 'Build a small browser-only task checklist. Add and check off tasks in component state. No backend, database, external APIs, authentication or secrets. Keep the app small and accessible.'},headers={'Idempotency-Key':'live-model-create'}).json()
            pid,owner=UUID(saved['project']['id']),UUID(saved['project']['owner_user_id'])
            body=PlanInput(kind='initial',request_id=UUID(saved['request_id']),
                base_brain_revision_id=UUID(saved['brain_revision_id']),base_version_id=None)
            attempt,prompt=planning.reserve(database,settings,owner,'live-model-plan',digest(body.model_dump_json()),pid,body)
            assert prompt
            async def plan() -> None:
                async with httpx.AsyncClient(trust_env=False,timeout=120,event_hooks={'request':[budget.reserve]}) as http:
                    provider=OpenAIPlanningProvider(client=http,api_key=settings.openai_api_key,
                        model=settings.openai_model,timeout_seconds=120)
                    result=await provider.create_context_plan(prompt,settings.planning_output_tokens)
                    planning.finish(database,settings,owner,attempt.id,result,None)
            asyncio.run(plan())
            proposals=client.get(f'/v1/projects/{pid}/planning/proposals').json()['items']
            assert len(proposals)==1 and proposals[0]['current_context']
            proposal=proposals[0]
            assert client.post(f'/v1/projects/{pid}/planning/proposals/{proposal["id"]}/review').status_code==200
            report['planning']='passed';report_path.write_text(json.dumps(report,indent=2)+'\n')
            response=client.post(f'/v1/projects/{pid}/builds',json={'proposal_id':proposal['id']},headers={'Idempotency-Key':'live-model-build'})
            assert response.status_code==202
            async def build() -> None:
                async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket),base_url='http://docker',trust_env=False,timeout=300) as engine, httpx.AsyncClient(trust_env=False,timeout=120,event_hooks={'request':[budget.reserve]}) as models:
                    assert await BuildWorker(database,settings,DockerSandbox(engine,image),source_provider(settings,models)).run_once()
            # Record only exception class and application frame, never values/locals/logs/secrets.
            exceptions: list[dict[str, str | int]]=[]
            def observed_exception(frame: FrameType, event: str, arg: object) -> 'TraceFunction':
                if isinstance(frame,FrameType) and event=='exception' and '/f01/' in frame.f_code.co_filename and isinstance(arg,tuple):
                    kind=arg[0]
                    if isinstance(kind,type) and kind.__name__ not in ('StopIteration','StopAsyncIteration','GeneratorExit'):
                        exceptions.append({'type':kind.__name__,'function':frame.f_code.co_name,'file':frame.f_code.co_filename.split('/f01/')[-1],'line':frame.f_lineno})
                return observed_exception
            sys.settrace(observed_exception);threading.settrace_all_threads(observed_exception)
            try:asyncio.run(build())
            finally:sys.settrace(None);threading.settrace_all_threads(None)
            state=client.get(f'/v1/projects/{pid}/workspace').json()
            build_record=client.get(f'/v1/projects/{pid}/builds').json()['items'][0]
            report['observed_build']={'phase':build_record['phase'],'error_code':build_record['run']['error_code'],'candidate_count':len(build_record['candidates']),'evidence_phases':[item['phase'] for item in build_record['evidence']]}
            if build_record['run']['error_code']=='EXECUTION_FAILED':report['unexpected_exception_frames']=exceptions[-30:]
            assert state['current_version'] is not None, build_record['run']['error_code']
            assert state['current_version']['mode']=='real'
            assert all(item['exit_code']==0 for item in build_record['evidence'] if item['phase'] in ('verification','test'))
            source_response=client.get(f'/v1/projects/{pid}/versions/{state["current_version"]["id"]}/source')
            assert source_response.status_code==200
            source=source_response.json()
            assert source['digest']==build_record['candidates'][-1]['digest']
            assert source['lineage']['brain_revision_id']==build_record['run']['input_brain_revision_id']
            report.update(source_generation='passed',docker='passed',repair_attempts=build_record['repair_attempts'],
                source_digest=source['digest'], run_id=build_record['run']['id'],version_id=state['current_version']['id'],
                input_brain_revision_id=build_record['run']['input_brain_revision_id'],
                evidence_phases=[item['phase'] for item in build_record['evidence']])
    except Exception:
        report['acceptance']='failed'
        raise
    finally:
        report_path.write_text(json.dumps(report,indent=2)+'\n')
        with database.session() as session:
            names=set(session.scalars(select(db.IsolatedPreview.container_name)))|set(session.scalars(select(db.ExecutionJob.container_name)))
        async def cleanup() -> None:
            async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=settings.sandbox_socket),base_url='http://docker',trust_env=False,timeout=30) as engine:
                for name in names:
                    if name: await DockerSandbox(engine,image).remove(name)
        asyncio.run(cleanup())
