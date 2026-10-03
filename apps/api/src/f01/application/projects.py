import base64
import binascii
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from f01.db.models import (
    BrainRevision,
    BuildEvent,
    BuildRun,
    DeploymentRecord,
    IdempotencyKey,
    Project,
    ProjectRequest,
    ProjectVersion,
    User,
)
from f01.db.session import Database
from f01.domain.brain import initial_brain
from f01.domain.errors import ApplicationError
from f01.domain.lifecycle import ACTIVE_STATUSES, Lifecycle
from f01.domain.projects import (
    BrainRevisionList,
    BrainRevisionRecord,
    BrainRevisionSummary,
    BrainView,
    CanonicalContext,
    CreateProject,
    DeploymentRecordView,
    EventList,
    EventPayload,
    EventRecord,
    PreviewState,
    Principal,
    ProjectCreated,
    ProjectList,
    ProjectSummary,
    RecordChange,
    RequestList,
    RequestRecord,
    RunRecord,
    UpdateProject,
    VersionList,
    VersionRecord,
    WorkspaceSnapshot,
)


def resolve_principal(database: Database, subject: str) -> Principal:
    with database.session() as session, session.begin():
        statement = (
            insert(User)
            .values(
                id=uuid4(),
                identity_issuer="f01-development",
                identity_subject=subject,
                display_name="Development owner",
            )
            .on_conflict_do_nothing(
                index_elements=["identity_issuer", "identity_subject"]
            )
        )
        session.execute(statement)
        user = session.scalar(
            select(User).where(
                User.identity_issuer == "f01-development",
                User.identity_subject == subject,
            )
        )
        assert user is not None
        return Principal(id=user.id, display_name=user.display_name)


def owned_project(
    session: Session, owner: UUID, project_id: UUID, *, lock: bool = False
) -> Project:
    statement = select(Project).where(
        Project.id == project_id, Project.owner_user_id == owner
    )
    if lock:
        statement = statement.with_for_update()
    project = session.scalar(statement)
    if project is None:
        raise ApplicationError("NOT_FOUND")
    return project


def etag(project: ProjectSummary) -> str:
    return f'"project-{project.id}-m{project.metadata_version}"'


def append_event(
    session: Session,
    project: Project,
    *,
    type: str,
    message: str,
    actor: UUID,
    run_id: UUID | None = None,
    request_id: UUID | None = None,
) -> None:
    # Caller holds the project row lock (or owns its uncommitted insertion).
    project.event_sequence += 1
    project.last_activity_at = datetime.now(UTC)
    payload = EventPayload(actor_user_id=actor).model_dump(
        mode="json", exclude_none=True
    )
    session.add(
        BuildEvent(
            id=uuid4(),
            project_id=project.id,
            run_id=run_id,
            request_id=request_id,
            sequence=project.event_sequence,
            type=type,
            severity="info",
            message=message,
            mode=None,
            payload=payload,
            occurred_at=project.last_activity_at,
        )
    )


def create_project(
    database: Database, principal: Principal, body: CreateProject, key: str, *, schedule: bool = False, real: bool = False
) -> ProjectCreated:
    now = datetime.now(UTC)
    request_hash = hashlib.sha256(
        json.dumps(
            body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    with database.session() as session, session.begin():
        session.execute(text("SET LOCAL lock_timeout = '2s'"))
        scope = (
            IdempotencyKey.user_id == principal.id,
            IdempotencyKey.method == "POST",
            IdempotencyKey.route_scope == "/v1/projects",
            IdempotencyKey.key == key,
        )
        existing = session.scalar(
            select(IdempotencyKey).where(*scope).with_for_update()
        )
        if existing is not None and existing.expires_at <= now:
            session.delete(existing)
            session.flush()
        reservation_id = uuid4()
        claimed = session.scalar(
            insert(IdempotencyKey)
            .values(
                id=reservation_id,
                user_id=principal.id,
                method="POST",
                route_scope="/v1/projects",
                key=key,
                request_hash=request_hash,
                response_status=0,
                response_body={},
                created_at=now,
                expires_at=now + timedelta(hours=24),
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "method", "route_scope", "key"]
            )
            .returning(IdempotencyKey.id)
        )
        if claimed is None:
            record = session.scalar(select(IdempotencyKey).where(*scope))
            assert record is not None
            if record.request_hash != request_hash:
                raise ApplicationError("IDEMPOTENCY_KEY_REUSED")
            if record.response_status == 0:
                raise ApplicationError("IDEMPOTENCY_IN_PROGRESS")
            return ProjectCreated.model_validate(record.response_body)
        result = _create_records(session, principal.id, body, now, schedule=schedule, real=real) if real else (_create_records(session, principal.id, body, now, schedule=True) if schedule else _create_records(session, principal.id, body, now))
        reservation = session.get(IdempotencyKey, reservation_id)
        assert reservation is not None
        reservation.response_status = 201
        reservation.response_body = result.model_dump(mode="json")
        return result


def _create_records(
    session: Session, owner: UUID, body: CreateProject, now: datetime, *, schedule: bool = False, real: bool = False
) -> ProjectCreated:
    project_id, request_id, brain_id, run_id = (uuid4() for _ in range(4))
    project = Project(
        id=project_id,
        owner_user_id=owner,
        title=body.title or body.brief.splitlines()[0][:60],
        lifecycle="understanding",
        current_brain_revision_id=brain_id,
        current_version_id=None,
        metadata_version=1,
        event_sequence=0,
        status_event_sequence=0,
        last_activity_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    session.flush()
    session.add(
        ProjectRequest(
            id=request_id,
            project_id=project_id,
            created_by=owner,
            kind="initial",
            text=body.brief,
            created_at=now,
        )
    )
    session.flush()
    session.add(
        BrainRevision(
            id=brain_id,
            project_id=project_id,
            revision=1,
            schema_version=1,
            source_request_id=request_id,
            source_run_id=None,
            content=initial_brain(request_id, body.brief).model_dump(mode="json"),
            created_at=now,
        )
    )
    session.flush()
    if real:
        project.lifecycle = "idle"
        append_event(session, project, type="project.created", message="Project saved. Review a plan before starting real execution.", actor=owner, request_id=request_id)
        project.status_event_sequence = project.event_sequence
        session.flush()
        return ProjectCreated(project=ProjectSummary.model_validate(project), project_url=f"/projects/{project_id}", request_id=request_id, brain_revision_id=brain_id, run_id=None, execution_mode="real")
    scenario = "crm-success" if "crm" in body.brief.casefold() else "generic-success"
    session.add(
        BuildRun(
            id=run_id,
            project_id=project_id,
            request_id=request_id,
            input_brain_revision_id=brain_id,
            attempt=1,
            mode="simulated",
            status="queued",
            scenario_id=scenario,
            scenario_version=1,
            step_cursor=0,
            next_step_at=now if schedule else None,
            created_at=now,
        )
    )
    session.flush()
    append_event(
        session,
        project,
        type="project.created",
        message="Project saved. Simulation demonstration queued; no application code will be executed.",
        actor=owner,
        run_id=run_id,
        request_id=request_id,
    )
    project.status_event_sequence = project.event_sequence
    session.flush()
    return ProjectCreated(
        project=ProjectSummary.model_validate(project),
        project_url=f"/projects/{project_id}",
        request_id=request_id,
        brain_revision_id=brain_id,
        run_id=run_id,
    )


def update_project(
    database: Database,
    owner: UUID,
    project_id: UUID,
    body: UpdateProject,
    if_match: str | None,
) -> ProjectSummary:
    with database.session() as session, session.begin():
        project = owned_project(session, owner, project_id, lock=True)
        if if_match is None:
            raise ApplicationError("PRECONDITION_REQUIRED")
        if if_match != etag(ProjectSummary.model_validate(project)):
            raise ApplicationError("METADATA_CONFLICT")
        changed = False
        if body.archived is True and project.archived_at is None:
            active = session.scalar(
                select(BuildRun.id).where(
                    BuildRun.project_id == project.id,
                    BuildRun.status.in_(ACTIVE_STATUSES),
                )
            )
            if active is not None:
                raise ApplicationError("ACTIVE_RUN_EXISTS")
            project.archived_at = datetime.now(UTC)
            append_event(
                session,
                project,
                type="project.archived",
                message="Project archived.",
                actor=owner,
            )
            changed = True
        elif body.archived is False and project.archived_at is not None:
            project.archived_at = None
            append_event(
                session,
                project,
                type="project.unarchived",
                message="Project unarchived.",
                actor=owner,
            )
            changed = True
        if body.title is not None and body.title != project.title:
            project.title = body.title
            append_event(
                session,
                project,
                type="project.renamed",
                message="Project renamed.",
                actor=owner,
            )
            changed = True
        if changed:
            project.metadata_version += 1
            project.updated_at = datetime.now(UTC)
        session.flush()
        return ProjectSummary.model_validate(project)


def encode_cursor(value: datetime | int, identifier: UUID) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(
            [
                value.isoformat() if isinstance(value, datetime) else value,
                str(identifier),
            ],
            separators=(",", ":"),
        ).encode()
    ).decode()


def decode_cursor(
    cursor: str, *, numbered: bool = False
) -> tuple[datetime | int, UUID]:
    try:
        data = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if not isinstance(data, list) or len(data) != 2 or not isinstance(data[1], str):
            raise ValueError()
        value = data[0]
        if numbered:
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 < value <= 2147483647
            ):
                raise ValueError()
        else:
            if not isinstance(value, str):
                raise ValueError()
            value = datetime.fromisoformat(value)
            if value.tzinfo is None:
                raise ValueError()
        return value, UUID(data[1])
    except (ValueError, TypeError, binascii.Error, OverflowError):
        raise ApplicationError("VALIDATION_ERROR") from None


def list_projects(
    database: Database,
    owner: UUID,
    *,
    q: str | None,
    status: Lifecycle | None,
    archived: bool,
    cursor: str | None,
    limit: int,
) -> ProjectList:
    with database.session() as session:
        query = select(Project).where(
            Project.owner_user_id == owner,
            Project.archived_at.is_not(None)
            if archived
            else Project.archived_at.is_(None),
        )
        if q:
            query = query.where(Project.title.icontains(q, autoescape=True))
        if status:
            query = query.where(Project.lifecycle == status)
        if cursor:
            timestamp, identifier = decode_cursor(cursor)
            query = query.where(
                tuple_(Project.updated_at, Project.id) < tuple_(timestamp, identifier)
            )
        rows = session.scalars(
            query.order_by(Project.updated_at.desc(), Project.id.desc()).limit(
                limit + 1
            )
        ).all()
        page = rows[:limit]
        next_cursor = (
            encode_cursor(page[-1].updated_at, page[-1].id)
            if len(rows) > limit
            else None
        )
        return ProjectList(
            items=[ProjectSummary.model_validate(row) for row in page],
            next_cursor=next_cursor,
        )


def read_project(database: Database, owner: UUID, project_id: UUID) -> ProjectSummary:
    with database.session() as session:
        return ProjectSummary.model_validate(owned_project(session, owner, project_id))


def read_revision(
    session: Session, project: Project, revision: int | None = None
) -> BrainRevisionRecord:
    query = select(BrainRevision).where(BrainRevision.project_id == project.id)
    query = (
        query.where(BrainRevision.id == project.current_brain_revision_id)
        if revision is None
        else query.where(BrainRevision.revision == revision)
    )
    row = session.scalar(query)
    if row is None:
        raise ApplicationError("NOT_FOUND")
    if row.schema_version != 1:
        raise ApplicationError("UNSUPPORTED_BRAIN_SCHEMA")
    try:
        return BrainRevisionRecord.model_validate(row)
    except ValidationError:
        raise ApplicationError("INTERNAL_ERROR") from None


def read_brain(
    database: Database, owner: UUID, project_id: UUID, revision: int | None
) -> BrainView:
    with database.session(snapshot=True) as session, session.begin():
        project = owned_project(session, owner, project_id)
        events = session.scalars(
            select(BuildEvent)
            .where(BuildEvent.project_id == project_id)
            .order_by(BuildEvent.sequence)
        ).all()
        context = CanonicalContext(
            requests=[
                RequestRecord.model_validate(row)
                for row in session.scalars(
                    select(ProjectRequest)
                    .where(ProjectRequest.project_id == project_id)
                    .order_by(ProjectRequest.created_at, ProjectRequest.id)
                )
            ],
            issue_events=[
                EventRecord.model_validate(row)
                for row in events
                if "issue_id" in row.payload or "resolves_issue_id" in row.payload
            ],
            versions=[
                VersionRecord.model_validate(row)
                for row in session.scalars(
                    select(ProjectVersion)
                    .where(ProjectVersion.project_id == project_id)
                    .order_by(ProjectVersion.number)
                )
            ],
            deployments=[
                DeploymentRecordView.model_validate(row)
                for row in session.scalars(
                    select(DeploymentRecord)
                    .where(DeploymentRecord.project_id == project_id)
                    .order_by(DeploymentRecord.created_at, DeploymentRecord.id)
                )
            ],
        )
        return BrainView(
            revision=read_revision(session, project, revision), context=context
        )


def read_requests(
    database: Database, owner: UUID, project_id: UUID, cursor: str | None, limit: int
) -> RequestList:
    with database.session(snapshot=True) as session, session.begin():
        owned_project(session, owner, project_id)
        query = select(ProjectRequest).where(ProjectRequest.project_id == project_id)
        if cursor:
            timestamp, identifier = decode_cursor(cursor)
            query = query.where(
                tuple_(ProjectRequest.created_at, ProjectRequest.id)
                < tuple_(timestamp, identifier)
            )
        rows = session.scalars(
            query.order_by(
                ProjectRequest.created_at.desc(), ProjectRequest.id.desc()
            ).limit(limit + 1)
        ).all()
        page = rows[:limit]
        return RequestList(
            items=[RequestRecord.model_validate(row) for row in page],
            next_cursor=encode_cursor(page[-1].created_at, page[-1].id)
            if len(rows) > limit
            else None,
        )


def read_revisions(
    database: Database, owner: UUID, project_id: UUID, cursor: str | None, limit: int
) -> BrainRevisionList:
    with database.session(snapshot=True) as session, session.begin():
        owned_project(session, owner, project_id)
        query = select(BrainRevision).where(BrainRevision.project_id == project_id)
        if cursor:
            number, identifier = decode_cursor(cursor, numbered=True)
            query = query.where(
                tuple_(BrainRevision.revision, BrainRevision.id)
                < tuple_(number, identifier)
            )
        rows = session.scalars(
            query.order_by(
                BrainRevision.revision.desc(), BrainRevision.id.desc()
            ).limit(limit + 1)
        ).all()
        page = rows[:limit]
        return BrainRevisionList(
            items=[BrainRevisionSummary.model_validate(row) for row in page],
            next_cursor=encode_cursor(page[-1].revision, page[-1].id)
            if len(rows) > limit
            else None,
        )


def workspace(database: Database, owner: UUID, project_id: UUID) -> WorkspaceSnapshot:
    with database.session(snapshot=True) as session, session.begin():
        project = owned_project(session, owner, project_id)
        latest = session.scalar(
            select(BuildRun)
            .where(BuildRun.project_id == project_id)
            .order_by(BuildRun.created_at.desc(), BuildRun.id.desc())
            .limit(1)
        )
        active = session.scalar(
            select(BuildRun).where(
                BuildRun.project_id == project_id, BuildRun.status.in_(ACTIVE_STATUSES)
            )
        )
        version = session.scalar(
            select(ProjectVersion).where(
                ProjectVersion.project_id == project_id,
                ProjectVersion.id == project.current_version_id,
            )
        )
        current_version = (
            VersionRecord.model_validate(version) if version is not None else None
        )
        events = session.scalars(
            select(BuildEvent)
            .where(
                BuildEvent.project_id == project_id,
                BuildEvent.sequence <= project.event_sequence,
            )
            .order_by(BuildEvent.sequence.desc())
            .limit(20)
        ).all()
        return WorkspaceSnapshot(
            project=ProjectSummary.model_validate(project),
            current_brain=read_revision(session, project),
            active_run=RunRecord.model_validate(active) if active else None,
            latest_run=RunRecord.model_validate(latest) if latest else None,
            current_version=current_version,
            preview=PreviewState(
                status="available" if current_version else "pending",
                descriptor=current_version.preview_descriptor
                if current_version
                else None,
                message="Verified isolated preview. Runtime availability is bounded by its expiry." if current_version and current_version.mode == "real" else "Internal demonstration fixture."
                if current_version
                else "Preview pending; no successful simulation version has been published.",
            ),
            recent_events=[EventRecord.model_validate(row) for row in reversed(events)],
            last_sequence=project.event_sequence,
        )


def record_change(
    database: Database, owner: UUID, project_id: UUID, body: RecordChange, key: str
) -> RequestRecord:
    now = datetime.now(UTC)
    request_hash = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    route = f"/v1/projects/{project_id}/requests"
    with database.session() as session, session.begin():
        session.execute(text("SET LOCAL lock_timeout = '2s'"))
        # Check ownership even on replay; a receipt never grants resource access.
        owned_project(session, owner, project_id)
        scope = (IdempotencyKey.user_id == owner, IdempotencyKey.method == "POST",
                 IdempotencyKey.route_scope == route, IdempotencyKey.key == key)
        existing = session.scalar(select(IdempotencyKey).where(*scope).with_for_update())
        if existing is not None and existing.expires_at <= now:
            session.delete(existing)
            session.flush()
        reservation_id = uuid4()
        claimed = session.scalar(
            insert(IdempotencyKey).values(
                id=reservation_id, user_id=owner, method="POST", route_scope=route, key=key,
                request_hash=request_hash, response_status=0, response_body={}, created_at=now,
                expires_at=now + timedelta(hours=24),
            ).on_conflict_do_nothing(index_elements=["user_id", "method", "route_scope", "key"])
            .returning(IdempotencyKey.id)
        )
        if claimed is None:
            receipt = session.scalar(select(IdempotencyKey).where(*scope))
            assert receipt is not None
            if receipt.request_hash != request_hash:
                raise ApplicationError("IDEMPOTENCY_KEY_REUSED")
            if receipt.response_status == 0:
                raise ApplicationError("IDEMPOTENCY_IN_PROGRESS")
            return RequestRecord.model_validate(receipt.response_body)
        project = owned_project(session, owner, project_id, lock=True)
        if project.archived_at is not None:
            raise ApplicationError("PROJECT_ARCHIVED")
        if body.base_brain_revision_id != project.current_brain_revision_id:
            raise ApplicationError("STALE_BRAIN_REVISION")
        if body.base_version_id != project.current_version_id:
            raise ApplicationError("STALE_BASE_VERSION")
        if session.scalar(select(BuildRun.id).where(
            BuildRun.project_id == project_id, BuildRun.status.in_(ACTIVE_STATUSES)
        )) is not None:
            raise ApplicationError("ACTIVE_RUN_EXISTS")
        row = ProjectRequest(
            id=uuid4(), project_id=project_id, created_by=owner, kind="change", text=body.text,
            base_brain_revision_id=body.base_brain_revision_id,
            base_version_id=body.base_version_id, created_at=now,
        )
        session.add(row)
        append_event(session, project, type="request.recorded", message="Change request recorded; no execution started.",
                     actor=owner, request_id=row.id)
        project.updated_at = project.last_activity_at
        session.flush()
        result = RequestRecord.model_validate(row)
        reservation = session.get(IdempotencyKey, reservation_id)
        assert reservation is not None
        reservation.response_status = 201
        reservation.response_body = result.model_dump(mode="json")
        return result


def read_events(database: Database, owner: UUID, project_id: UUID, after_sequence: int, limit: int, run_id: UUID | None = None) -> EventList:
    with database.session(snapshot=True) as session, session.begin():
        project = owned_project(session, owner, project_id)
        if after_sequence > project.event_sequence:
            raise ApplicationError("VALIDATION_ERROR")
        if run_id is not None and session.scalar(select(BuildRun.id).where(BuildRun.project_id == project_id, BuildRun.id == run_id)) is None:
            raise ApplicationError("NOT_FOUND")
        query = select(BuildEvent).where(
            BuildEvent.project_id == project_id, BuildEvent.sequence > after_sequence,
            BuildEvent.sequence <= project.event_sequence,
        )
        if run_id is not None:
            query = query.where(BuildEvent.run_id == run_id)
        rows = session.scalars(query.order_by(BuildEvent.sequence).limit(limit + 1)).all()
        page = rows[:limit]
        return EventList(items=[EventRecord.model_validate(row) for row in page],
                         next_cursor=str(page[-1].sequence) if len(rows) > limit else None)


def read_versions(database: Database, owner: UUID, project_id: UUID, cursor: str | None, limit: int) -> VersionList:
    with database.session(snapshot=True) as session, session.begin():
        owned_project(session, owner, project_id)
        query = select(ProjectVersion).where(ProjectVersion.project_id == project_id)
        if cursor:
            number, identifier = decode_cursor(cursor, numbered=True)
            query = query.where(tuple_(ProjectVersion.number, ProjectVersion.id) < tuple_(number, identifier))
        rows = session.scalars(query.order_by(ProjectVersion.number.desc(), ProjectVersion.id.desc()).limit(limit + 1)).all()
        page = rows[:limit]
        return VersionList(items=[VersionRecord.model_validate(row) for row in page],
                           next_cursor=encode_cursor(page[-1].number, page[-1].id) if len(rows) > limit else None)


def read_version(database: Database, owner: UUID, project_id: UUID, version_id: UUID) -> VersionRecord:
    with database.session() as session:
        owned_project(session, owner, project_id)
        row = session.scalar(select(ProjectVersion).where(ProjectVersion.project_id == project_id, ProjectVersion.id == version_id))
        if row is None:
            raise ApplicationError("NOT_FOUND")
        return VersionRecord.model_validate(row)
