from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from f01.api.dependencies import get_database, get_principal
from f01.api.errors import ErrorEnvelope
from f01.application import execution as service
from f01.config import Settings, get_settings
from f01.db.models import ExecutionJob, IsolatedPreview, SourceCandidate
from f01.db.session import Database
from f01.domain.errors import ApplicationError
from f01.domain.execution import StartBuild, BuildDetail, BuildList
from f01.domain.projects import Principal, RunRecord
from f01.domain.source import SourceArtifact
from f01.application.projects import owned_project
import json

router=APIRouter(prefix="/v1/projects/{project_id}",tags=["Real builds"],responses={code:{"model":ErrorEnvelope} for code in (401,404,409,422,429,503)})
DB=Annotated[Database,Depends(get_database)]
Owner=Annotated[Principal,Depends(get_principal)]
Config=Annotated[Settings,Depends(get_settings)]
Key=Annotated[str,Header(min_length=1,max_length=200,pattern=r"^[A-Za-z0-9._:-]+$")]

@router.post('/builds',response_model=RunRecord,status_code=202)
def start(project_id:UUID,body:StartBuild,request:Request,database:DB,owner:Owner,settings:Config,idempotency_key:Key)->RunRecord:
    auth=getattr(request.state,'auth_session',None)
    return service.queue(database,settings,owner.id,project_id,body,idempotency_key,auth.id if auth else None)

@router.get('/builds',response_model=BuildList)
def builds(project_id:UUID,database:DB,owner:Owner)->BuildList:
    with database.session() as session:
        owned_project(session,owner.id,project_id)
        ids=session.scalars(select(ExecutionJob.run_id).where(ExecutionJob.project_id==project_id).order_by(ExecutionJob.created_at.desc()).limit(20)).all()
    return BuildList(items=[service.detail(database,owner.id,project_id,identifier) for identifier in ids])

@router.get('/builds/{run_id}',response_model=BuildDetail)
def build(project_id:UUID,run_id:UUID,database:DB,owner:Owner)->BuildDetail:
    return service.detail(database,owner.id,project_id,run_id)

@router.post('/builds/{run_id}/cancel',response_model=RunRecord)
def cancel(project_id:UUID,run_id:UUID,database:DB,owner:Owner)->RunRecord:
    return service.cancel(database,owner.id,project_id,run_id)

@router.post('/builds/{run_id}/retry',response_model=RunRecord,status_code=202)
def retry(project_id:UUID,run_id:UUID,request:Request,database:DB,owner:Owner,settings:Config,idempotency_key:Key)->RunRecord:
    with database.session() as session:
        owned_project(session,owner.id,project_id)
        job=session.scalar(select(ExecutionJob).where(ExecutionJob.project_id==project_id,ExecutionJob.run_id==run_id))
        if job is None:raise ApplicationError('NOT_FOUND')
        plan=job.plan_id
    auth=getattr(request.state,'auth_session',None)
    return service.queue(database,settings,owner.id,project_id,StartBuild(proposal_id=plan),idempotency_key,auth.id if auth else None,run_id)

@router.get('/versions/{version_id}/source',response_model=SourceArtifact)
def source(project_id:UUID,version_id:UUID,database:DB,owner:Owner)->SourceArtifact:
    with database.session(snapshot=True) as session:
        owned_project(session,owner.id,project_id)
        preview=session.scalar(select(IsolatedPreview).where(IsolatedPreview.project_id==project_id,IsolatedPreview.version_id==version_id))
        if preview is None:raise ApplicationError('NOT_FOUND')
        candidate=session.get(SourceCandidate,preview.candidate_id);assert candidate is not None
        return SourceArtifact.model_validate_json(json.dumps(candidate.source))
