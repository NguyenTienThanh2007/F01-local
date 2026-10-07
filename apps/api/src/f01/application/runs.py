"""Owned simulation commands and reads. Every mutation locks project before run."""
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from f01.application.projects import owned_project, read_revision, encode_cursor, decode_cursor
from f01.db.models import BuildEvent, BuildRun, DeploymentRecord, IdempotencyKey, Project, ProjectRequest
from f01.db.session import Database
from f01.domain.errors import ApplicationError
from f01.domain.lifecycle import ACTIVE_STATUSES, lifecycle_after_terminal, transition_status
from f01.domain.projects import DeploymentList, DeploymentRecordView, EventPayload, RunList, RunRecord, StartRun


def simulation_event(session: Session, project: Project, run: BuildRun, now: datetime, *, type: str, message: str, payload: EventPayload | None = None, severity: str = "info", deduplication_key: str | None = None) -> int:
    project.event_sequence += 1
    project.last_activity_at = project.updated_at = now
    session.add(BuildEvent(id=uuid4(), project_id=project.id, run_id=run.id, request_id=run.request_id,
        sequence=project.event_sequence, deduplication_key=deduplication_key, type=type, phase=run.phase,
        severity=severity, mode="simulated", message=message,
        payload=(payload or EventPayload()).model_dump(mode="json", exclude_none=True), occurred_at=now))
    return project.event_sequence


def owned_run(session: Session, project_id: UUID, run_id: UUID, *, lock: bool = False) -> BuildRun:
    query = select(BuildRun).where(BuildRun.project_id == project_id, BuildRun.id == run_id)
    row = session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise ApplicationError("NOT_FOUND")
    return row


def reserve(session: Session, owner: UUID, route: str, key: str, body: dict[str, object], now: datetime) -> tuple[IdempotencyKey | None, RunRecord | None]:
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    scope = (IdempotencyKey.user_id == owner, IdempotencyKey.method == "POST", IdempotencyKey.route_scope == route, IdempotencyKey.key == key)
    existing = session.scalar(select(IdempotencyKey).where(*scope).with_for_update())
    if existing is not None and existing.expires_at <= now:
        session.delete(existing)
        session.flush()
    identifier = uuid4()
    claimed = session.scalar(insert(IdempotencyKey).values(id=identifier, user_id=owner, method="POST", route_scope=route,
        key=key, request_hash=digest, response_status=0, response_body={}, created_at=now, expires_at=now + timedelta(hours=24))
        .on_conflict_do_nothing(index_elements=["user_id", "method", "route_scope", "key"]).returning(IdempotencyKey.id))
    if claimed is None:
        receipt = session.scalar(select(IdempotencyKey).where(*scope))
        assert receipt is not None
        if receipt.request_hash != digest:
            raise ApplicationError("IDEMPOTENCY_KEY_REUSED")
        if receipt.response_status == 0:
            raise ApplicationError("IDEMPOTENCY_IN_PROGRESS")
        return None, RunRecord.model_validate(receipt.response_body)
    receipt = session.get(IdempotencyKey, identifier)
    assert receipt is not None
    return receipt, None


def available(session: Session, project: Project, brain_id: UUID, version_id: UUID | None) -> None:
    from f01.application.releases import guard
    guard(session, project.id)
    if project.archived_at is not None:
        raise ApplicationError("PROJECT_ARCHIVED")
    if project.current_brain_revision_id != brain_id:
        raise ApplicationError("STALE_BRAIN_REVISION")
    if project.current_version_id != version_id:
        raise ApplicationError("STALE_BASE_VERSION")
    read_revision(session, project)
    if session.scalar(select(BuildRun.id).where(BuildRun.project_id == project.id, BuildRun.status.in_(ACTIVE_STATUSES))) is not None:
        raise ApplicationError("ACTIVE_RUN_EXISTS")


def queue(session: Session, project: Project, receipt: IdempotencyKey, request_id: UUID, brain_id: UUID, version_id: UUID | None, name: str, now: datetime, actor: UUID, retry: BuildRun | None = None) -> RunRecord:
    run = BuildRun(id=uuid4(), project_id=project.id, request_id=request_id, input_brain_revision_id=brain_id,
        base_version_id=version_id, retry_of_run_id=retry.id if retry else None, attempt=retry.attempt + 1 if retry else 1,
        mode="simulated", status="queued", scenario_id=name, scenario_version=1, step_cursor=0, next_step_at=now, created_at=now)
    session.add(run)
    session.flush()
    project.lifecycle = "understanding"
    project.status_event_sequence = simulation_event(session, project, run, now, type="run.queued",
        message="Simulation: demonstration queued. Arbitrary requested changes may leave the bundled sample unchanged.", payload=EventPayload(actor_user_id=actor))
    session.flush()
    result = RunRecord.model_validate(run)
    receipt.response_status = 202
    receipt.response_body = result.model_dump(mode="json")
    return result


def start_run(database: Database, owner: UUID, project_id: UUID, body: StartRun, key: str, *, change_scenario: str = "auto", now: datetime | None = None) -> RunRecord:
    now = now or datetime.now(UTC)
    with database.session() as session, session.begin():
        session.execute(text("SET LOCAL lock_timeout = '2s'"))
        owned_project(session, owner, project_id)
        receipt, replay = reserve(session, owner, f"/v1/projects/{project_id}/runs", key, body.model_dump(mode="json"), now)
        if replay is not None:
            return replay
        assert receipt is not None
        project = owned_project(session, owner, project_id, lock=True)
        if project.current_version_id:
            from f01.db.models import ProjectVersion
            version = session.get(ProjectVersion, project.current_version_id)
            if version and version.mode == "real": raise ApplicationError("REAL_BUILD_COMMAND_REQUIRED")
        request = session.scalar(select(ProjectRequest).where(ProjectRequest.project_id == project_id, ProjectRequest.id == body.request_id))
        if request is None:
            raise ApplicationError("NOT_FOUND")
        brain = request.base_brain_revision_id if request.kind == "change" else body.expected_brain_revision_id
        assert brain is not None
        if body.expected_brain_revision_id != brain:
            raise ApplicationError("STALE_BRAIN_REVISION")
        if request.kind == "initial" and read_revision(session, project).source_run_id is not None:
            raise ApplicationError("STALE_BRAIN_REVISION")
        available(session, project, brain, request.base_version_id)
        name = "crm-success" if "crm" in read_revision(session, project).content.product.summary.text.casefold() else "generic-success"
        if request.kind == "change" and change_scenario != "auto":
            name = change_scenario
        return queue(session, project, receipt, request.id, brain, request.base_version_id, name, now, owner)


def retry_run(database: Database, owner: UUID, project_id: UUID, run_id: UUID, key: str, *, now: datetime | None = None) -> RunRecord:
    now = now or datetime.now(UTC)
    with database.session() as session, session.begin():
        session.execute(text("SET LOCAL lock_timeout = '2s'"))
        owned_project(session, owner, project_id)
        receipt, replay = reserve(session, owner, f"/v1/projects/{project_id}/runs/{run_id}/retry", key, {}, now)
        if replay is not None:
            return replay
        assert receipt is not None
        project = owned_project(session, owner, project_id, lock=True)
        prior = owned_run(session, project_id, run_id, lock=True)
        if prior.mode != "simulated":
            raise ApplicationError("REAL_BUILD_COMMAND_REQUIRED")
        if prior.status != "failed":
            raise ApplicationError("RUN_NOT_RETRYABLE")
        available(session, project, prior.input_brain_revision_id, prior.base_version_id)
        name = "crm-success" if "crm" in read_revision(session, project).content.product.summary.text.casefold() else "generic-success"
        return queue(session, project, receipt, prior.request_id, prior.input_brain_revision_id, prior.base_version_id, name, now, owner, prior)


def cancel_run(database: Database, owner: UUID, project_id: UUID, run_id: UUID, *, now: datetime | None = None) -> RunRecord:
    now = now or datetime.now(UTC)
    with database.session() as session, session.begin():
        project = owned_project(session, owner, project_id, lock=True)
        run = owned_run(session, project_id, run_id, lock=True)
        if run.mode == "real":
            raise ApplicationError("REAL_BUILD_COMMAND_REQUIRED")
        if run.status in ACTIVE_STATUSES:
            run.status = transition_status(run.status, "canceled")  # type: ignore[arg-type]
            run.finished_at = run.last_heartbeat_at = now
            run.next_step_at = None
            project.lifecycle = lifecycle_after_terminal("canceled", has_version=project.current_version_id is not None)
            project.status_event_sequence = simulation_event(session, project, run, now, type="run.canceled",
                message="Simulation: demonstration canceled. The prior successful preview is preserved.", payload=EventPayload(actor_user_id=owner))
            session.flush()
        return RunRecord.model_validate(run)


def read_run(database: Database, owner: UUID, project_id: UUID, run_id: UUID) -> RunRecord:
    with database.session() as session:
        owned_project(session, owner, project_id)
        return RunRecord.model_validate(owned_run(session, project_id, run_id))


def read_runs(database: Database, owner: UUID, project_id: UUID, cursor: str | None, limit: int) -> RunList:
    with database.session(snapshot=True) as session, session.begin():
        owned_project(session, owner, project_id)
        query = select(BuildRun).where(BuildRun.project_id == project_id)
        if cursor:
            timestamp, identifier = decode_cursor(cursor)
            query = query.where(tuple_(BuildRun.created_at, BuildRun.id) < tuple_(timestamp, identifier))
        rows = session.scalars(query.order_by(BuildRun.created_at.desc(), BuildRun.id.desc()).limit(limit + 1)).all()
        page = rows[:limit]
        return RunList(items=[RunRecord.model_validate(r) for r in page], next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None)


def read_deployments(database: Database, owner: UUID, project_id: UUID, cursor: str | None = None, limit: int = 20) -> DeploymentList:
    with database.session() as session:
        owned_project(session, owner, project_id)
        query = select(DeploymentRecord).where(DeploymentRecord.project_id == project_id)
        if cursor:
            timestamp, identifier = decode_cursor(cursor)
            query = query.where(tuple_(DeploymentRecord.created_at, DeploymentRecord.id) < tuple_(timestamp, identifier))
        rows = session.scalars(query.order_by(DeploymentRecord.created_at.desc(), DeploymentRecord.id.desc()).limit(limit + 1)).all()
        page = rows[:limit]
        return DeploymentList(items=[DeploymentRecordView.model_validate(r) for r in page], next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None)
