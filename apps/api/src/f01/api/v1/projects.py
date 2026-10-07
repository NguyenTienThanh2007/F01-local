from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text

from f01.api.dependencies import get_database, get_principal, authenticated_bearer
from f01.api.stream import replay_cursor, stream_events
from f01.application import runs
from f01.config import Settings, get_settings
from f01.api.errors import ApplicationError, ErrorEnvelope
from f01.application import projects as service
from f01.db.session import Database
from f01.domain.lifecycle import Lifecycle
from f01.domain.projects import (
    BrainRevisionList,
    BrainView,
    CreateProject,
    EventList,
    RecordChange,
    RequestRecord,
    VersionList,
    VersionRecord,
    Principal,
    ProjectCreated,
    ProjectList,
    ProjectSummary,
    RequestList,
    SessionView,
    UpdateProject,
    WorkspaceSnapshot,
    Capabilities, StartRun, RetryRun, RunRecord, RunList, DeploymentList,
)

router = APIRouter(
    prefix="/v1",
    tags=["Projects"],
    responses={
        code: {"model": ErrorEnvelope}
        for code in (401, 404, 409, 412, 422, 428, 500, 503)
    },
)
DatabaseDependency = Annotated[Database, Depends(get_database)]
PrincipalDependency = Annotated[Principal, Depends(get_principal)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
CommandKey = Annotated[str, Header(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageCursor = Annotated[str | None, Query(max_length=500)]


def metadata_headers(response: Response, project: ProjectSummary) -> None:
    response.headers["ETag"] = service.etag(project)
    response.headers["Cache-Control"] = "no-store"


@router.get("/session", response_model=SessionView)
def session(request: Request, principal: PrincipalDependency, settings: SettingsDependency) -> SessionView:
    auth_session = getattr(request.state, "auth_session", None)
    return SessionView(principal=principal, capabilities=Capabilities(simulation_runner=settings.simulation_runner_enabled, execution_mode=settings.execution_mode, real_generation=settings.real_execution_enabled, source_artifacts=settings.real_execution_enabled), expires_at=auth_session.expires_at if auth_session else None)


@router.post("/projects", response_model=ProjectCreated, status_code=201)
def create_project(
    body: CreateProject,
    response: Response,
    database: DatabaseDependency,
    principal: PrincipalDependency,
    settings: SettingsDependency,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> ProjectCreated:
    result = service.create_project(database, principal, body, idempotency_key, schedule=settings.simulation_runner_enabled, real=settings.real_execution_enabled)
    response.headers["Location"] = f"/v1/projects/{result.project.id}"
    # A replay's metadata is the saved creation snapshot; read Location for current state.
    metadata_headers(response, result.project)
    return result


@router.get("/projects", response_model=ProjectList)
def list_projects(
    database: DatabaseDependency,
    principal: PrincipalDependency,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: Lifecycle | None = None,
    archived: bool = False,
    cursor: PageCursor = None,
    limit: PageLimit = 20,
) -> ProjectList:
    return service.list_projects(
        database,
        principal.id,
        q=q,
        status=status,
        archived=archived,
        cursor=cursor,
        limit=limit,
    )


@router.get("/projects/{project_id}", response_model=ProjectSummary)
def read_project(
    project_id: UUID,
    response: Response,
    database: DatabaseDependency,
    principal: PrincipalDependency,
) -> ProjectSummary:
    result = service.read_project(database, principal.id, project_id)
    metadata_headers(response, result)
    return result


@router.patch("/projects/{project_id}", response_model=ProjectSummary)
def update_project(
    project_id: UUID,
    body: UpdateProject,
    response: Response,
    database: DatabaseDependency,
    principal: PrincipalDependency,
    if_match: Annotated[str | None, Header(max_length=200)] = None,
) -> ProjectSummary:
    result = service.update_project(database, principal.id, project_id, body, if_match)
    metadata_headers(response, result)
    return result


@router.get("/projects/{project_id}/workspace", response_model=WorkspaceSnapshot)
def workspace(
    project_id: UUID, database: DatabaseDependency, principal: PrincipalDependency
) -> WorkspaceSnapshot:
    return service.workspace(database, principal.id, project_id)


@router.get("/projects/{project_id}/brain", response_model=BrainView)
def brain(
    project_id: UUID,
    database: DatabaseDependency,
    principal: PrincipalDependency,
    revision: Annotated[int | None, Query(gt=0, le=2147483647)] = None,
) -> BrainView:
    return service.read_brain(database, principal.id, project_id, revision)


@router.get("/projects/{project_id}/brain/revisions", response_model=BrainRevisionList)
def revisions(
    project_id: UUID,
    database: DatabaseDependency,
    principal: PrincipalDependency,
    cursor: PageCursor = None,
    limit: PageLimit = 20,
) -> BrainRevisionList:
    return service.read_revisions(database, principal.id, project_id, cursor, limit)


@router.get("/projects/{project_id}/requests", response_model=RequestList)
def requests(
    project_id: UUID,
    database: DatabaseDependency,
    principal: PrincipalDependency,
    cursor: PageCursor = None,
    limit: PageLimit = 20,
) -> RequestList:
    return service.read_requests(database, principal.id, project_id, cursor, limit)


@router.get("/health/ready", tags=["Health"])
def ready(database: DatabaseDependency) -> dict[str, str]:
    with database.engine.connect() as connection:
        if connection.scalar(text("SELECT to_regclass('alembic_version')")) is None:
            raise ApplicationError("DATABASE_NOT_READY")
        versions = connection.scalars(
            text("SELECT version_num FROM alembic_version")
        ).all()
        if versions != ["0005_release_target"]:
            raise ApplicationError("DATABASE_NOT_READY")
    return {"status": "ready"}


@router.post("/projects/{project_id}/requests", response_model=RequestRecord, status_code=201)
def record_change(
    project_id: UUID, body: RecordChange, database: DatabaseDependency, principal: PrincipalDependency,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")],
) -> RequestRecord:
    return service.record_change(database, principal.id, project_id, body, idempotency_key)


@router.get("/projects/{project_id}/events", response_model=EventList)
def events(
    project_id: UUID, database: DatabaseDependency, principal: PrincipalDependency,
    after_sequence: Annotated[int, Query(ge=0, le=2147483647)] = 0, limit: PageLimit = 20,
    run_id: UUID | None = None,
) -> EventList:
    return service.read_events(database, principal.id, project_id, after_sequence, limit, run_id)


@router.get("/projects/{project_id}/versions", response_model=VersionList)
def versions(
    project_id: UUID, database: DatabaseDependency, principal: PrincipalDependency,
    cursor: PageCursor = None, limit: PageLimit = 20,
) -> VersionList:
    return service.read_versions(database, principal.id, project_id, cursor, limit)


@router.get("/projects/{project_id}/versions/{version_id}", response_model=VersionRecord)
def version(
    project_id: UUID, version_id: UUID, database: DatabaseDependency, principal: PrincipalDependency,
) -> VersionRecord:
    return service.read_version(database, principal.id, project_id, version_id)


@router.post("/projects/{project_id}/runs", response_model=RunRecord, status_code=202)
def start_run(project_id: UUID, body: StartRun, database: DatabaseDependency, principal: PrincipalDependency,
    settings: SettingsDependency, idempotency_key: CommandKey) -> RunRecord:
    return runs.start_run(database, principal.id, project_id, body, idempotency_key, change_scenario=settings.simulation_change_scenario)


@router.get("/projects/{project_id}/runs", response_model=RunList)
def list_runs(project_id: UUID, database: DatabaseDependency, principal: PrincipalDependency, cursor: PageCursor = None, limit: PageLimit = 20) -> RunList:
    return runs.read_runs(database, principal.id, project_id, cursor, limit)


@router.get("/projects/{project_id}/runs/{run_id}", response_model=RunRecord)
def run_details(project_id: UUID, run_id: UUID, database: DatabaseDependency, principal: PrincipalDependency) -> RunRecord:
    return runs.read_run(database, principal.id, project_id, run_id)


@router.post("/projects/{project_id}/runs/{run_id}/cancel", response_model=RunRecord)
def cancel_run(project_id: UUID, run_id: UUID, body: RetryRun, database: DatabaseDependency, principal: PrincipalDependency) -> RunRecord:
    return runs.cancel_run(database, principal.id, project_id, run_id)


@router.post("/projects/{project_id}/runs/{run_id}/retry", response_model=RunRecord, status_code=202)
def retry_run(project_id: UUID, run_id: UUID, body: RetryRun, database: DatabaseDependency, principal: PrincipalDependency, idempotency_key: CommandKey) -> RunRecord:
    return runs.retry_run(database, principal.id, project_id, run_id, idempotency_key)


@router.get("/projects/{project_id}/deployments", response_model=DeploymentList)
def deployments(project_id: UUID, database: DatabaseDependency, principal: PrincipalDependency, cursor: PageCursor = None, limit: PageLimit = 20) -> DeploymentList:
    return runs.read_deployments(database, principal.id, project_id, cursor, limit)


@router.get("/projects/{project_id}/events/stream", response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}})
def events_stream(project_id: UUID, request: Request, database: DatabaseDependency, principal: PrincipalDependency,
    settings: SettingsDependency, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(authenticated_bearer)],
    after_sequence: str | None = None, last_event_id: Annotated[str | None, Header()] = None) -> StreamingResponse:
    cursor = replay_cursor(after_sequence, last_event_id)
    service.read_events(database, principal.id, project_id, cursor, 1)  # validate ownership/cursor before headers
    assert credentials is not None
    def authorized() -> bool:
        from f01.application.identity import authenticate_session
        try:
            identity, _ = authenticate_session(database, settings, request.app.state.oidc_verifier, credentials.credentials,
                request.headers.get("x-f01-session", ""), None, False)
            return identity.id == principal.id
        except ApplicationError:
            return False
    return StreamingResponse(stream_events(database, principal.id, project_id, cursor, settings, credentials.credentials, request.is_disconnected,
        authorized=authorized if settings.auth_mode == "oidc" else None),
        media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
