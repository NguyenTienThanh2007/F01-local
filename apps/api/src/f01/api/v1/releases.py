"""Owner-only fixed release commands, separate from simulation deployment history."""
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Request
from f01.api.dependencies import get_database, get_principal
from f01.api.errors import ErrorEnvelope
from f01.application import releases as service
from f01.config import Settings, get_settings
from f01.db.session import Database
from f01.domain.projects import Principal
from f01.domain.releases import ArtifactPreparation, PrepareRelease, PromoteRelease, ReleaseDetail, ReleaseWorkspace, HostingSetup, SetupReleaseTarget

router = APIRouter(prefix='/v1/projects/{project_id}', tags=['Production releases'], responses={code: {'model': ErrorEnvelope} for code in (401, 404, 409, 422, 503)})
DB = Annotated[Database, Depends(get_database)]
Owner = Annotated[Principal, Depends(get_principal)]
Config = Annotated[Settings, Depends(get_settings)]
Key = Annotated[str, Header(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9._:-]+$')]


@router.get('/releases', response_model=ReleaseWorkspace)
def workspace(project_id: UUID, database: DB, owner: Owner, settings: Config) -> ReleaseWorkspace:
    return service.workspace(database, settings, owner.id, project_id)


@router.post('/release-artifacts', response_model=ArtifactPreparation, status_code=202)
def prepare(project_id: UUID, body: PrepareRelease, database: DB, owner: Owner, settings: Config, idempotency_key: Key) -> ArtifactPreparation:
    return service.prepare(database, settings, owner.id, project_id, body, idempotency_key)


@router.post('/releases', response_model=ReleaseDetail, status_code=202)
def promote(project_id: UUID, body: PromoteRelease, request: Request, database: DB, owner: Owner, settings: Config, idempotency_key: Key) -> ReleaseDetail:
    auth = getattr(request.state, 'auth_session', None)
    return service.promote(database, settings, owner.id, project_id, body, idempotency_key, auth.id if auth else None)


@router.post('/releases/{release_id}/cancel', response_model=ReleaseDetail)
def cancel(project_id: UUID, release_id: UUID, database: DB, owner: Owner) -> ReleaseDetail:
    return service.cancel(database, owner.id, project_id, release_id)


@router.post('/release-target', response_model=HostingSetup, status_code=202)
def setup_target(project_id: UUID, body: SetupReleaseTarget, request: Request, database: DB, owner: Owner, settings: Config, idempotency_key: Key) -> HostingSetup:
    auth = getattr(request.state, 'auth_session', None)
    return service.setup_target(database, settings, owner.id, project_id, body, idempotency_key, auth.id if auth else None)


@router.post('/release-artifacts/{preparation_id}/retry', response_model=ArtifactPreparation, status_code=202)
def retry_preparation(project_id: UUID, preparation_id: UUID, body: PrepareRelease, database: DB, owner: Owner, settings: Config, idempotency_key: Key) -> ArtifactPreparation:
    return service.prepare(database, settings, owner.id, project_id, body, idempotency_key, preparation_id)


@router.post('/releases/{release_id}/retry', response_model=ReleaseDetail, status_code=202)
def retry_release(project_id: UUID, release_id: UUID, body: PromoteRelease, request: Request, database: DB, owner: Owner, settings: Config, idempotency_key: Key) -> ReleaseDetail:
    auth = getattr(request.state, 'auth_session', None)
    return service.promote(database, settings, owner.id, project_id, body, idempotency_key, auth.id if auth else None, release_id)


@router.post('/releases/{release_id}/resume', response_model=ReleaseDetail)
def resume_release(project_id: UUID, release_id: UUID, database: DB, owner: Owner) -> ReleaseDetail:
    return service.resume(database, owner.id, project_id, release_id)
