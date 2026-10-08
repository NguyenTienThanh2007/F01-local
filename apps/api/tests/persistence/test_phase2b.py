"""Persistence/orchestration tests use controlled evidence, never pretend Docker ran."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4
from typing import Any
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from f01.application import execution as service, planning
from f01.application.projects import create_project, resolve_principal, record_change, workspace
from f01.config import Settings
from f01.db.models import BuildRun, ExecutionJob, Project, SourceCandidate, VerificationEvidence, IsolatedPreview, AuthSession
from f01.db.session import Database
from f01.domain.context_planning import PlanInput, ContextPlan, PlanningResult
from f01.domain.errors import ApplicationError
from f01.domain.execution import CommandEvidence, Diagnostic, StartBuild
from f01.domain.projects import CreateProject, RecordChange
from f01.domain.planning import ProjectPlan
from f01.domain.source import GenerationContext, GenerationResult, PutFile, SourceArtifact, SourceProposal
from f01.execution.docker import DockerSandbox, SandboxError
from f01.execution.sandbox import CommandPhase
from f01.execution.worker import BuildWorker

IMAGE='sha256:'+'a'*64

class SourceProvider:
    def __init__(self, broken:bool=False, forever:bool=False)->None:
        self.broken,self.forever,self.calls=broken,forever,0
    async def propose_source(self,context:GenerationContext,maximum_output_tokens:int)->GenerationResult:
        self.calls+=1
        broken=self.forever or self.broken and not context.repair_evidence
        content="export default function Page(){ const broken: number = 'bad'; return <main>{broken}</main>; }" if broken else "export default function Page(){ return <main>Verified dashboard</main>; }"
        if context.lineage.version_id is not None and not broken:
            content="'use client';import {useState} from 'react';export default function Page(){const [priority,setPriority]=useState('all');const leads=[{name:'Harbor',priority:'high'},{name:'Orchard',priority:'low'}];return <main><h1>Verified dashboard</h1><label htmlFor='priority'>Priority filter</label><select id='priority' value={priority} onChange={e=>setPriority(e.target.value)}><option value='all'>All leads</option><option value='high'>High priority</option></select><ul>{leads.filter(x=>priority==='all'||x.priority===priority).map(x=><li key={x.name}>{x.name}</li>)}</ul></main>; }"
        base=context.base_source
        files={f.path:f for f in base.files} if base else {}
        edits=[PutFile(operation='put',path='app/page.tsx',prior_sha256=files['app/page.tsx'].sha256 if base else None,content=content+'\n'*self.calls)]
        if base is None:
            edits.append(PutFile(operation='put',path='tests/dashboard.test.mjs',prior_sha256=None,content="import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';test('dashboard is rendered in the built artifact',()=>{assert.match(fs.readFileSync('.next/server/app/index.html','utf8'),/Verified dashboard/);});"))
            edits.insert(0,PutFile(operation='put',path='app/layout.tsx',prior_sha256=None,content="import type {ReactNode} from 'react';export default function Layout({children}:{children:ReactNode}){return <html><body>{children}</body></html>;}"))
        return GenerationResult(proposal=SourceProposal(schema_version=1,recipe='next-web-v1',base_digest=base.digest if base else None,edits=tuple(edits)),input_tokens=100,output_tokens=200)

class ControlledSandbox(DockerSandbox):
    def __init__(self)->None:
        self.image=IMAGE;self.sources:dict[str,SourceArtifact]={};self.names:set[str]=set();self.removed:list[str]=[];self.reject_cleanup=False
    async def ready(self)->None:pass
    async def create(self,name:str,project:UUID,run:UUID,preview_path:str)->None:self.names.add(name)
    async def remove(self,name:str)->None:
        if self.reject_cleanup:raise SandboxError('SANDBOX_ENGINE_UNAVAILABLE')
        self.names.discard(name);self.removed.append(name)
    async def materialize(self,name:str,source:SourceArtifact,alive:Any)->CommandEvidence:
        self.sources[name]=source
        return self.result('materialization')
    def result(self,phase:str,failed:bool=False)->CommandEvidence:
        return CommandEvidence(phase=phase,argv=['controlled'],exit_code=1 if failed else 0,duration_ms=1,diagnostics=[Diagnostic(code='TS2322',path='app/page.tsx',line=1)] if failed else [],image_id=IMAGE)
    async def command(self,name:str,phase:CommandPhase,tests:tuple[str,...],alive:Any)->CommandEvidence:
        return self.result(phase.value,phase==CommandPhase.TYPECHECK and any('const broken:' in f.content for f in self.sources[name].files))
    async def start_preview(self,name:str,source:SourceArtifact,alive:Any,preview_path:str)->CommandEvidence:return self.result('verification')

@pytest.fixture
def configured(project_settings:Settings)->Settings:
    return project_settings.model_copy(update={'real_execution_enabled':True,'execution_mode':'real','sandbox_image_id':IMAGE,'preview_origin':'http://127.0.0.1:3031','factory_origin':'http://localhost:3000','planning_daily_token_budget':10000000,'planning_requests_per_minute':30})

def setup_build(database:Database,configured:Settings,project_plan:ProjectPlan)->tuple[UUID,UUID,StartBuild]:
    owner=resolve_principal(database,'real-owner')
    created=create_project(database,owner,CreateProject(brief='Build a browser-only dashboard with a leads overview.'),str(uuid4()),real=True)
    pid=created.project.id
    return owner.id,pid,review_plan(database,configured,project_plan,owner.id,pid,created.request_id,'initial')

def review_plan(database:Database,configured:Settings,project_plan:ProjectPlan,owner:UUID,pid:UUID,request:UUID,kind:str)->StartBuild:
    saved=workspace(database,owner,pid)
    body=PlanInput(kind=kind,request_id=request,base_brain_revision_id=saved.project.current_brain_revision_id,base_version_id=saved.project.current_version_id)
    attempt,_=planning.reserve(database,configured,owner,str(uuid4()),str(uuid4()),pid,body)
    result=planning.finish(database,configured,owner,attempt.id,PlanningResult(content=ContextPlan(plan=project_plan,scope=['Browser dashboard'],assumptions=['No external services'],acceptance_criteria=['Show the overview'],out_of_scope=['Production deployment'])))
    assert result.proposal
    planning.review(database,owner,pid,result.proposal.id)
    return StartBuild(proposal_id=result.proposal.id)

def test_atomic_publication_and_bounded_repair(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan)
    run=service.queue(database,configured,owner,pid,body,'once')
    assert service.queue(database,configured,owner,pid,body,'once').id==run.id
    source=SourceProvider(broken=True);sandbox=ControlledSandbox()
    assert asyncio.run(BuildWorker(database,configured,sandbox,source).run_once())
    detail=service.detail(database,owner,pid,run.id)
    assert detail.run.status=='succeeded' and detail.repair_attempts==1 and len(detail.candidates)==2
    assert source.calls==2 and len(sandbox.removed)==1 and len(sandbox.names)==1
    saved=workspace(database,owner,pid)
    assert saved.current_version and saved.current_version.mode=='real' and saved.preview.descriptor
    assert {d.provenance.source for d in saved.current_brain.content.design_decisions}>={'model_proposed','generated','verified','published'}
    assert saved.current_brain.content.product.summary.provenance.source=='user_request'
    assert any(e.exit_code==1 for e in detail.evidence)
    # Repair history remains immutable; progress cannot reuse the old candidate's checks.
    assert detail.current_candidate_evidence and all(e.exit_code == 0 for e in detail.current_candidate_evidence)
    assert {e.phase for e in detail.current_candidate_evidence} >= {"materialization", "install", "typecheck", "build", "verification"}
    assert detail.progress_updated_at and detail.progress_updated_at >= detail.candidates[-1].created_at
    assert detail.progress_sequence == workspace(database, owner, pid).last_sequence
    with database.session() as session:assert session.scalar(select(IsolatedPreview.id))

@pytest.mark.parametrize('repair',[False,True])
def test_rejected_generation_has_actionable_code_and_never_publishes(database:Database,configured:Settings,project_plan:ProjectPlan,repair:bool)->None:
    owner,pid,body=setup_build(database,configured,project_plan)
    run=service.queue(database,configured,owner,pid,body,'rejected-source')
    class RejectedSource(SourceProvider):
        async def propose_source(self,context:GenerationContext,maximum_output_tokens:int)->GenerationResult:
            if repair and context.base_source is None:return await super().propose_source(context,maximum_output_tokens)
            self.calls+=1
            edits=tuple(PutFile(operation='put',path=f.path,prior_sha256=f.sha256,content=f.content) for f in context.base_source.files) if context.base_source else (PutFile(operation='put',path='app/page.tsx',prior_sha256=None,content='export default function Page(){return <main>Missing layout</main>}'),)
            return GenerationResult(proposal=SourceProposal(schema_version=1,recipe='next-web-v1',base_digest=context.base_source.digest if context.base_source else None,edits=edits),input_tokens=100,output_tokens=200)
    provider=RejectedSource(broken=repair);sandbox=ControlledSandbox()
    assert asyncio.run(BuildWorker(database,configured,sandbox,provider).run_once())
    detail=service.detail(database,owner,pid,run.id)
    assert detail.run.status=='failed' and detail.run.error_code=='SOURCE_PROPOSAL_REJECTED'
    assert workspace(database,owner,pid).current_version is None and not sandbox.names
    assert len(detail.candidates)==(1 if repair else 0)
    if repair:assert any(e.exit_code!=0 for e in detail.evidence)

def test_failed_update_preserves_last_good_version(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan)
    service.queue(database,configured,owner,pid,body,'first');sandbox=ControlledSandbox()
    asyncio.run(BuildWorker(database,configured,sandbox,SourceProvider()).run_once())
    before=workspace(database,owner,pid)
    request=record_change(database,owner,pid,RecordChange(text='Add a priority filter to the existing leads overview.',base_brain_revision_id=before.project.current_brain_revision_id,base_version_id=before.project.current_version_id),str(uuid4()))
    plan=review_plan(database,configured,project_plan,owner,pid,request.id,'change')
    run=service.queue(database,configured,owner,pid,plan,'failed-update')
    source=SourceProvider(forever=True)
    asyncio.run(BuildWorker(database,configured,sandbox,source).run_once())
    after=workspace(database,owner,pid)
    assert after.current_version==before.current_version and after.current_brain==before.current_brain and after.preview==before.preview
    assert service.detail(database,owner,pid,run.id).run.error_code=='REPAIR_EXHAUSTED'
    assert source.calls==configured.repair_attempts+1 and len(sandbox.names)==1

def test_duplicate_workers_fenced_and_concurrency_bounded(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan);service.queue(database,configured,owner,pid,body,'workers')
    with ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(lambda _:service.claim(database,configured),range(2)))
    assert sum(c is not None for c in claims)==1
    identifier,token=next(c for c in claims if c)
    assert not service.heartbeat(database,configured,identifier,uuid4())
    assert service.heartbeat(database,configured,identifier,token)

def test_cancel_retains_cleanup_identity_and_recovery_retries(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan);run=service.queue(database,configured,owner,pid,body,'cancel')
    claimed=service.claim(database,configured);assert claimed
    sandbox=ControlledSandbox();worker=BuildWorker(database,configured,sandbox,SourceProvider())
    name=sandbox.name(claimed[0],1,1)
    with database.session() as session,session.begin():
        job=session.get(ExecutionJob,claimed[0]);assert job;job.container_name=name
    service.cancel(database,owner,pid,run.id);assert not service.heartbeat(database,configured,*claimed)
    sandbox.reject_cleanup=True;asyncio.run(worker.recover())
    with database.session() as session:
        saved=session.get(ExecutionJob,claimed[0]);assert saved and saved.container_name==name
    sandbox.reject_cleanup=False;asyncio.run(worker.recover())
    with database.session() as session:
        saved=session.get(ExecutionJob,claimed[0]);assert saved and saved.container_name is None

def test_provider_uncertainty_never_automatically_replayed(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan);run=service.queue(database,configured,owner,pid,body,'uncertain')
    claimed=service.claim(database,configured);assert claimed
    with database.session() as session,session.begin():
        job=session.get(ExecutionJob,claimed[0]);assert job;job.phase='generation_pending';job.lease_until=service.now()-timedelta(seconds=1)
    provider=SourceProvider();asyncio.run(BuildWorker(database,configured,ControlledSandbox(),provider).run_once())
    assert provider.calls==0 and service.detail(database,owner,pid,run.id).run.error_code=='PROVIDER_OUTCOME_UNKNOWN'

def test_restart_reverifies_saved_source_without_provider_retry(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan);run=service.queue(database,configured,owner,pid,body,'restart')
    claimed=service.claim(database,configured);assert claimed
    provider=SourceProvider();worker=BuildWorker(database,configured,ControlledSandbox(),provider)
    context,_=worker.initial(claimed[0]);source=asyncio.run(worker.generate(*claimed,context));worker.save_candidate(*claimed,source)
    with database.session() as session,session.begin():
        job=session.get(ExecutionJob,claimed[0]);assert job;job.lease_until=service.now()-timedelta(seconds=1)
    asyncio.run(worker.run_once())
    assert provider.calls==1 and service.detail(database,owner,pid,run.id).run.status=='succeeded'

def test_stale_input_and_cross_owner_rejected(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan)
    foreign=resolve_principal(database,'foreign')
    with pytest.raises(ApplicationError,match='NOT_FOUND'):service.queue(database,configured,foreign.id,pid,body,'foreign')
    run=service.queue(database,configured,owner,pid,body,'stale')
    with database.session() as session,session.begin():
        project=session.get(Project,pid);assert project;project.metadata_version+=1
    assert service.claim(database,configured) is None
    assert service.detail(database,owner,pid,run.id).run.error_code=='STALE_RUN_CONTEXT'

def test_publication_rejects_missing_evidence_and_expired_lease(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan);service.queue(database,configured,owner,pid,body,'proof')
    claimed=service.claim(database,configured);assert claimed
    worker=BuildWorker(database,configured,ControlledSandbox(),SourceProvider());context,_=worker.initial(claimed[0]);source=asyncio.run(worker.generate(*claimed,context));candidate=worker.save_candidate(*claimed,source)
    with pytest.raises(ApplicationError,match='VERIFICATION_REQUIRED'):service.publish(database,configured,*claimed,candidate)
    with pytest.raises(DBAPIError),database.engine.begin() as connection:connection.execute(text('UPDATE source_candidates SET digest=:digest WHERE id=:id'),{'digest':'0'*64,'id':candidate})
    with database.session() as session,session.begin():
        job=session.get(ExecutionJob,claimed[0]);assert job;job.lease_until=service.now()-timedelta(seconds=1)
    with pytest.raises(ApplicationError,match='LEASE_LOST'):service.publish(database,configured,*claimed,candidate)

@pytest.mark.parametrize('field,value',[('preview_origin','http://localhost:3031'),('sandbox_image_id','next:latest')])
def test_execution_configuration_fails_closed(configured:Settings,field:str,value:str)->None:
    from pydantic import ValidationError
    data=configured.model_dump();data[field]=value
    with pytest.raises(ValidationError):Settings(**data,_env_file=None)


def test_source_budget_stops_before_model_dispatch(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan);run=service.queue(database,configured,owner,pid,body,'budget')
    low=configured.model_copy(update={'source_run_token_budget':10000})
    provider=SourceProvider();asyncio.run(BuildWorker(database,low,ControlledSandbox(),provider).run_once())
    assert provider.calls==0 and service.detail(database,owner,pid,run.id).run.error_code=='SOURCE_BUDGET_EXCEEDED'


def test_deadline_and_session_revocation_block_publication(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan);run=service.queue(database,configured,owner,pid,body,'deadline')
    with database.session() as session,session.begin():
        job=session.scalar(select(ExecutionJob).where(ExecutionJob.run_id==run.id));assert job;job.deadline_at=service.now()-timedelta(seconds=1)
    provider=SourceProvider();asyncio.run(BuildWorker(database,configured,ControlledSandbox(),provider).run_once())
    assert provider.calls==0 and service.detail(database,owner,pid,run.id).run.error_code=='BUILD_TIMEOUT'


def test_cross_project_evidence_composite_fk(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan);service.queue(database,configured,owner,pid,body,'lineage')
    claimed=service.claim(database,configured);assert claimed
    worker=BuildWorker(database,configured,ControlledSandbox(),SourceProvider());context,_=worker.initial(claimed[0]);source=asyncio.run(worker.generate(*claimed,context));candidate=worker.save_candidate(*claimed,source)
    _,other,_=setup_build(database,configured,project_plan)
    with pytest.raises(DBAPIError),database.session() as session,session.begin():session.add(VerificationEvidence(id=uuid4(),project_id=other,candidate_id=candidate,phase='build',content={},created_at=service.now()))


def test_phase2a_upgrade_preserves_existing_records(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    owner,pid,body=setup_build(database,configured,project_plan)
    before=workspace(database,owner,pid)
    config=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    with database.engine.begin() as connection:
        config.attributes['connection']=connection
        command.downgrade(config,'0002_phase2a')
        assert connection.scalar(text("SELECT id FROM planning_proposals WHERE id=:id"),{'id':body.proposal_id})==body.proposal_id
        command.upgrade(config,'head');command.check(config)
    assert workspace(database,owner,pid)==before


def test_revoked_session_prevents_worker_dispatch(database:Database,configured:Settings,project_plan:ProjectPlan)->None:
    owner,pid,body=setup_build(database,configured,project_plan)
    sid=uuid4()
    with database.session() as session,session.begin():session.add(AuthSession(id=sid,user_id=owner,session_hash='0'*64,csrf_hash='1'*64,access_hash='2'*64,access_encrypted='synthetic sealed access',created_at=service.now(),expires_at=service.now()+timedelta(minutes=10),last_seen_at=service.now(),revoked_at=service.now()))
    run=service.queue(database,configured,owner,pid,body,'revoked',sid)
    provider=SourceProvider();asyncio.run(BuildWorker(database,configured,ControlledSandbox(),provider).run_once())
    assert provider.calls==0 and service.detail(database,owner,pid,run.id).run.error_code=='AUTHENTICATION_REQUIRED'
