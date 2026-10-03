"""Bounded owned context, durable usage reservations and immutable proposals."""
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from f01.application.identity import digest
from f01.application.projects import owned_project, append_event
from f01.config import Settings
from f01.db.models import AuthSession, BrainRevision, BuildEvent, PlanningAttempt, PlanningProposal, PlanReview, Project, ProjectRequest, ProjectVersion, User
from f01.db.session import Database
from f01.domain.brain import BrainContent, Statement
from f01.domain.context_planning import PlanInput, ProposalRecord, AttemptRecord, PlanningResult, ContextPlan, UsageView
from f01.domain.planning import ProjectPlan
from f01.domain.errors import ApplicationError
from f01.providers.prompts import CONTEXT_INSTRUCTIONS, PLANNING_INSTRUCTIONS

def encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def excerpt(value: str, maximum: int) -> dict[str, object]:
    clipped = value.encode()[:maximum].decode(errors="ignore")
    return {"text": clipped, "truncated": clipped != value}

def statement(value: Statement, maximum: int) -> dict[str, object]:
    return {**excerpt(value.text, maximum), "provenance": value.provenance.model_dump(mode="json")}

def has_clipping(value: object) -> bool:
    if isinstance(value, dict): return value.get("truncated") is True or any(has_clipping(item) for item in value.values())
    if isinstance(value, list): return any(has_clipping(item) for item in value)
    return False

def fingerprint(session: Session, project: Project) -> dict[str, object]:
    latest = session.scalar(select(ProjectRequest.id).where(ProjectRequest.project_id == project.id).order_by(ProjectRequest.created_at.desc(), ProjectRequest.id.desc()).limit(1))
    return {"brain_revision_id": str(project.current_brain_revision_id), "version_id": str(project.current_version_id) if project.current_version_id else None,
        "metadata_version": project.metadata_version, "latest_request_id": str(latest),
        "request_sequence": session.scalar(select(func.max(BuildEvent.sequence)).where(BuildEvent.project_id == project.id, BuildEvent.type == "request.recorded")) or 0}

def current(session: Session, project: Project, context: dict[str, object]) -> bool:
    return context.get("bases") == fingerprint(session, project)

def lock_owner(session: Session, user_id: UUID) -> None:
    # Serialize planning transactions without blocking FK FOR KEY SHARE checks
    # from existing project/request writes that already hold the project lock.
    if session.scalar(select(User).where(User.id == user_id).with_for_update(key_share=True)) is None:
        raise ApplicationError("NOT_FOUND")

def assemble(session: Session, project: Project, body: PlanInput, settings: Settings) -> dict[str, object]:
    if project.archived_at: raise ApplicationError("PROJECT_ARCHIVED")
    if body.base_brain_revision_id != project.current_brain_revision_id or body.base_version_id != project.current_version_id:
        raise ApplicationError("PLANNING_STALE_CONTEXT")
    request = session.scalar(select(ProjectRequest).where(ProjectRequest.project_id == project.id, ProjectRequest.id == body.request_id))
    brain = session.get(BrainRevision, project.current_brain_revision_id)
    if request is None: raise ApplicationError("NOT_FOUND")
    if request.kind != body.kind: raise ApplicationError("VALIDATION_ERROR")
    if body.kind == "change" and (request.base_brain_revision_id != body.base_brain_revision_id or request.base_version_id != body.base_version_id):
        raise ApplicationError("PLANNING_STALE_CONTEXT")
    if brain is None or brain.schema_version != 1: raise ApplicationError("UNSUPPORTED_BRAIN_SCHEMA")
    content = BrainContent.model_validate(brain.content)
    original = session.get(ProjectRequest, content.original_request_id)
    assert original is not None
    history = session.scalars(select(ProjectRequest).where(ProjectRequest.project_id == project.id, ProjectRequest.id.not_in([original.id, request.id]))
        .order_by(ProjectRequest.created_at.desc(), ProjectRequest.id.desc()).limit(5)).all()
    version = session.get(ProjectVersion, project.current_version_id) if project.current_version_id else None
    requirements = [{"id": item.requirement_id, "priority": item.priority, "assumption": item.assumption, "requirement": excerpt(item.text, 800),
        "acceptance_criteria": [statement(criterion, 300) for criterion in item.acceptance_criteria[:2]], "provenance": item.provenance.model_dump(mode="json")} for item in content.product.requirements[:8]]
    context: dict[str, object] = {"schema_version": 1, "kind": body.kind, "project_id": str(project.id), "title": project.title,
        "request_id": str(request.id), "bases": fingerprint(session, project), "brain_revision": brain.revision,
        "original_brief": {"request_id": str(original.id), **excerpt(original.text, 6000)}, "intent": excerpt(request.text, 6000),
        "requirements": requirements, "summary": statement(content.product.summary, 1000),
        "current_plan": [{"step_id": step.step_id, "status": step.status, "requirement_ids": step.requirement_ids, **statement(step, 500)} for step in content.plan[:4]],
        "stack": {key: statement(getattr(content.stack, key), 400) for key in ("frontend", "backend", "database", "rationale")},
        "architecture": {"overview": statement(content.architecture.overview, 800), "evidence": content.architecture.evidence},
        "constraints": [statement(item, 300) for item in content.constraints[:4]],
        "open_questions": [statement(item, 300) for item in content.open_questions[:4]],
        "decisions": [{"id": item.decision_id, "choice": excerpt(item.choice, 300), "reason": excerpt(item.reason, 300), "provenance": item.provenance.model_dump(mode="json")} for item in content.design_decisions[:4]],
        "relevant_history": [{"request_id": str(item.id), "kind": item.kind, **excerpt(item.text, 600)} for item in history],
        "version": {"id": str(version.id), "number": version.number, "mode": version.mode, "summary": version.summary} if version else None,
        "source": {"available": False, "reason": "No generated source exists in Phase 2A."},
        "execution": "All existing execution/version evidence is Simulation. Planning is proposed work.",
        "selection": {"requirements_total": len(content.product.requirements), "requirements_included": len(requirements), "history_limit": 5, "context_truncated": False}}
    selection = context["selection"]
    assert isinstance(selection, dict)
    selection["context_truncated"] = has_clipping(context) or len(content.product.requirements) > 8 or any(len(items) > 4 for items in (content.plan, content.constraints, content.open_questions, content.design_decisions))
    if len(encode(context).encode()) > settings.planning_context_bytes:
        context["relevant_history"] = []
        context["original_brief"] = {"request_id": str(original.id), **excerpt(original.text, 1000)}
        context["intent"] = excerpt(request.text, 2000)
        context["requirements"] = requirements[:2]
        context["selection"] = {"requirements_total": len(content.product.requirements), "requirements_included": min(2, len(requirements)), "history_limit": 0, "context_truncated": True}
    if len(encode(context).encode()) > settings.planning_context_bytes: raise ApplicationError("PLANNING_CONTEXT_TOO_LARGE")
    return context

def proposal_record(session: Session, project: Project, row: PlanningProposal) -> ProposalRecord:
    original = row.context.get("original_brief")
    manifest = {"bases": row.context.get("bases"), "brain_revision": row.context.get("brain_revision"), "selection": row.context.get("selection"),
        "context_sha256": digest(encode(row.context)), "source_available": False,
        "sources": {"original_request_id": original.get("request_id") if isinstance(original, dict) else None,
            "request_id": str(row.request_id), "brain_revision_id": str(row.brain_revision_id), "version_id": str(row.version_id) if row.version_id else None}}
    return ProposalRecord(id=row.id, attempt_id=row.attempt_id, project_id=row.project_id, request_id=row.request_id, brain_revision_id=row.brain_revision_id,
        version_id=row.version_id, kind=row.kind, content=ContextPlan.model_validate(row.content), context=manifest, provider=row.provider, model=row.model,
        created_at=row.created_at, current_context=current(session, project, row.context), reviewed=session.scalar(select(PlanReview.id).where(PlanReview.proposal_id == row.id)) is not None)

def attempt_record(session: Session, row: PlanningAttempt, project: Project | None) -> AttemptRecord:
    if row.status == "pending" and row.deadline_at <= datetime.now(UTC):
        row.status, row.error_code, row.finished_at = "abandoned", "PLANNING_ABANDONED", datetime.now(UTC)
    proposal = session.scalar(select(PlanningProposal).where(PlanningProposal.attempt_id == row.id))
    return AttemptRecord(id=row.id, project_id=row.project_id, status=row.status, reserved_tokens=row.reserved_tokens, input_tokens=row.input_tokens,
        output_tokens=row.output_tokens, error_code=row.error_code, created_at=row.created_at, deadline_at=row.deadline_at,
        proposal=proposal_record(session, project, proposal) if proposal and project else None)

def reserve(database: Database, settings: Settings, user_id: UUID, key: str, request_hash: str,
    project_id: UUID | None, body: PlanInput | None = None, idea: str | None = None) -> tuple[AttemptRecord, str | None]:
    now = datetime.now(UTC)
    with database.session() as session, session.begin():
        lock_owner(session, user_id)
        project = owned_project(session, user_id, project_id, lock=True) if project_id else None
        existing = session.scalar(select(PlanningAttempt).where(PlanningAttempt.user_id == user_id, PlanningAttempt.key == key))
        if existing:
            if existing.request_hash != request_hash or existing.project_id != project_id: raise ApplicationError("IDEMPOTENCY_KEY_REUSED")
            return attempt_record(session, existing, project), None
        context = assemble(session, project, body, settings) if project is not None and body is not None else {"idea": idea}
        prompt = encode(context)
        # UTF-8 byte count + instructions/overhead is a conservative token reservation, not a tokenizer claim.
        schema = ContextPlan.model_json_schema() if project else ProjectPlan.model_json_schema()
        estimated = len(prompt.encode()) + len((CONTEXT_INSTRUCTIONS if project else PLANNING_INSTRUCTIONS).encode()) + len(encode(schema).encode()) + 512
        if estimated > settings.planning_input_tokens: raise ApplicationError("PLANNING_CONTEXT_TOO_LARGE")
        for old in session.scalars(select(PlanningAttempt).where(PlanningAttempt.user_id == user_id, PlanningAttempt.status == "pending", PlanningAttempt.deadline_at <= now)):
            old.status, old.error_code, old.finished_at = "abandoned", "PLANNING_ABANDONED", now
        session.flush()
        if session.scalar(select(PlanningAttempt.id).where(PlanningAttempt.user_id == user_id, PlanningAttempt.status == "pending").limit(1)):
            raise ApplicationError("PLANNING_IN_PROGRESS")
        minute_count = session.scalar(select(func.count()).select_from(PlanningAttempt).where(PlanningAttempt.user_id == user_id, PlanningAttempt.created_at >= now-timedelta(minutes=1))) or 0
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_count, used = session.execute(select(func.count(), func.coalesce(func.sum(PlanningAttempt.reserved_tokens), 0)).where(PlanningAttempt.user_id == user_id, PlanningAttempt.created_at >= day)).one()
        if minute_count >= settings.planning_requests_per_minute or day_count >= settings.planning_requests_per_day:
            raise ApplicationError("PLANNING_RATE_LIMITED")
        reserved = estimated + settings.planning_output_tokens
        if used + reserved > settings.planning_daily_token_budget: raise ApplicationError("PLANNING_BUDGET_EXCEEDED")
        for secret in (settings.openai_api_key, settings.auth_gateway_token, settings.oidc_client_secret, settings.dev_api_token, settings.session_encryption_key):
            if secret and len(secret.get_secret_value()) >= 8 and secret.get_secret_value() in prompt:
                raise ApplicationError("VALIDATION_ERROR")
        row = PlanningAttempt(id=uuid4(), user_id=user_id, project_id=project_id, key=key, request_hash=request_hash, status="pending", context=context,
            reserved_tokens=reserved, created_at=now, deadline_at=now+timedelta(seconds=settings.planning_timeout_seconds+15))
        session.add(row); session.flush()
        return attempt_record(session, row, project), prompt

def finish(database: Database, settings: Settings, user_id: UUID, attempt_id: UUID, result: PlanningResult | None,
    error: str | None = None, auth_session_id: UUID | None = None) -> AttemptRecord:
    now = datetime.now(UTC)
    with database.session() as session, session.begin():
        lock_owner(session, user_id)
        auth = session.get(AuthSession, auth_session_id, with_for_update=True) if auth_session_id else None
        row = session.scalar(select(PlanningAttempt).where(PlanningAttempt.id == attempt_id, PlanningAttempt.user_id == user_id).with_for_update())
        if row is None: raise ApplicationError("NOT_FOUND")
        project = owned_project(session, user_id, row.project_id, lock=True) if row.project_id else None
        view = attempt_record(session, row, project)
        if row.status != "pending": return view
        if auth_session_id and (auth is None or auth.user_id != user_id or auth.revoked_at or auth.expires_at <= now or auth.last_seen_at + timedelta(seconds=settings.session_idle_seconds) <= now): error = "AUTHENTICATION_REQUIRED"
        if project and (project.archived_at or not current(session, project, row.context)): error = "PLANNING_STALE_CONTEXT"
        row.finished_at = now
        if error:
            row.status, row.error_code = ("stale" if error == "PLANNING_STALE_CONTEXT" else "failed"), error
        else:
            row.status = "succeeded"
            if result and project:
                result = PlanningResult.model_validate(result)
                row.input_tokens, row.output_tokens = result.input_tokens, result.output_tokens
                bases = row.context["bases"]
                assert isinstance(bases, dict)
                proposal = PlanningProposal(id=uuid4(), attempt_id=row.id, project_id=project.id, user_id=user_id, request_id=UUID(str(row.context["request_id"])),
                    brain_revision_id=UUID(str(bases["brain_revision_id"])), version_id=UUID(str(bases["version_id"])) if bases["version_id"] else None,
                    kind=str(row.context["kind"]), context=row.context, content=result.content.model_dump(mode="json"),
                    provider=settings.planning_provider, model=settings.openai_model, created_at=now)
                session.add(proposal)
                append_event(session, project, type="planning.proposed", message="Real planning proposal saved. Proposed work only; no application execution occurred.", actor=user_id)
        session.flush()
        return attempt_record(session, row, project)

def read_attempt(database: Database, user_id: UUID, project_id: UUID, attempt_id: UUID, cancel: bool = False) -> AttemptRecord:
    with database.session() as session, session.begin():
        lock_owner(session, user_id)
        project = owned_project(session, user_id, project_id)
        row = session.scalar(select(PlanningAttempt).where(PlanningAttempt.id == attempt_id, PlanningAttempt.user_id == user_id, PlanningAttempt.project_id == project_id).with_for_update())
        if row is None: raise ApplicationError("NOT_FOUND")
        if cancel: project = owned_project(session, user_id, project_id, lock=True)
        view = attempt_record(session, row, project)
        if cancel and row.status == "pending":
            row.status, row.error_code, row.finished_at = "canceled", "PLANNING_CANCELED", datetime.now(UTC)
            view = attempt_record(session, row, project)
        return view

def proposals(database: Database, user_id: UUID, project_id: UUID) -> list[ProposalRecord]:
    with database.session(snapshot=True) as session:
        project = owned_project(session, user_id, project_id)
        rows = session.scalars(select(PlanningProposal).where(PlanningProposal.project_id == project_id).order_by(PlanningProposal.created_at.desc(), PlanningProposal.id.desc()).limit(40))
        return [proposal_record(session, project, row) for row in rows]

def review(database: Database, user_id: UUID, project_id: UUID, proposal_id: UUID) -> ProposalRecord:
    with database.session() as session, session.begin():
        lock_owner(session, user_id)
        project = owned_project(session, user_id, project_id, lock=True)
        row = session.scalar(select(PlanningProposal).where(PlanningProposal.id == proposal_id, PlanningProposal.project_id == project_id))
        if row is None: raise ApplicationError("NOT_FOUND")
        if not current(session, project, row.context) or project.archived_at: raise ApplicationError("PLANNING_STALE_CONTEXT")
        if session.scalar(select(PlanReview.id).where(PlanReview.proposal_id == row.id)) is None:
            session.add(PlanReview(id=uuid4(), proposal_id=row.id, user_id=user_id, created_at=datetime.now(UTC)))
            append_event(session, project, type="planning.reviewed", message="Planning proposal reviewed. No generation or execution was started.", actor=user_id)
            session.flush()
        return proposal_record(session, project, row)

def usage(database: Database, settings: Settings, user_id: UUID) -> UsageView:
    day = datetime.now(UTC).replace(hour=0,minute=0,second=0,microsecond=0)
    with database.session() as session:
        count,tokens = session.execute(select(func.count(),func.coalesce(func.sum(PlanningAttempt.reserved_tokens),0)).where(PlanningAttempt.user_id==user_id,PlanningAttempt.created_at>=day)).one()
        return UsageView(requests_used=count,requests_per_day=settings.planning_requests_per_day,requests_per_minute=settings.planning_requests_per_minute,
            tokens_reserved=tokens,daily_token_budget=settings.planning_daily_token_budget,input_token_limit=settings.planning_input_tokens,
            output_token_limit=settings.planning_output_tokens,resets_at=day+timedelta(days=1))
