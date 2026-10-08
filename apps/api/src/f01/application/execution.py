"""Owned execution persistence, fencing and atomic publication. No generated host code."""
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from sqlalchemy import func, select, text, or_
from sqlalchemy.orm import Session
from f01.application.identity import digest
from f01.application.planning import current, fingerprint, lock_owner
from f01.application.projects import owned_project, read_revision
from f01.application.runs import available, reserve
from f01.config import Settings
from f01.db.models import AuthSession, BrainRevision, BuildEvent, BuildRun, ExecutionJob, IdempotencyKey, IsolatedPreview, PlanReview, PlanningAttempt, PlanningProposal, Project, ProjectRequest, ProjectVersion, SourceCandidate, VerificationEvidence
from f01.db.session import Database
from f01.domain.brain import BrainContent, DesignDecision, Provenance
from f01.domain.context_planning import ContextPlan
from f01.domain.errors import ApplicationError
from f01.domain.execution import BuildDetail, CandidateMetadata, CommandEvidence, StartBuild
from f01.domain.projects import EventPayload, RunRecord
from f01.domain.source import GenerationContext, SourceArtifact, SourceLineage
from f01.application.source_artifacts import validate_artifact

LEASE_SECONDS = 30


def now() -> datetime:
    return datetime.now(UTC)


def emit(session: Session, project: Project, run: BuildRun, phase: str, *, candidate: UUID | None = None, evidence: UUID | None = None, issue: str | None = None, resolves: str | None = None, provenance: str | None = None, failed: bool = False) -> int:
    project.event_sequence += 1
    project.last_activity_at = project.updated_at = now()
    session.add(BuildEvent(id=uuid4(), project_id=project.id, run_id=run.id, request_id=run.request_id,
        sequence=project.event_sequence, type=f"execution.{phase}", phase=run.phase, mode="real",
        severity="error" if failed else "info", message=f"Real execution: {phase.replace('_', ' ')}{' failed' if failed else ''}.",
        payload=EventPayload(execution_phase=phase, candidate_id=candidate, evidence_id=evidence, issue_id=issue,
            resolves_issue_id=resolves, provenance=provenance).model_dump(mode="json", exclude_none=True), occurred_at=now()))
    return project.event_sequence


def assemble(session: Session, project: Project, proposal: PlanningProposal) -> GenerationContext:
    brain = read_revision(session, project).content
    request = session.get(ProjectRequest, proposal.request_id)
    assert request is not None
    source: SourceArtifact | None = None
    if project.current_version_id:
        preview = session.scalar(select(IsolatedPreview).where(IsolatedPreview.project_id == project.id, IsolatedPreview.version_id == project.current_version_id))
        if preview is None: raise ApplicationError("SOURCE_BASE_UNAVAILABLE")
        candidate = session.get(SourceCandidate, preview.candidate_id)
        assert candidate is not None
        source = SourceArtifact.model_validate_json(json.dumps(candidate.source))
        validate_artifact(source)
    plan = ContextPlan.model_validate(proposal.content)
    history = session.scalars(select(ProjectRequest).where(ProjectRequest.project_id == project.id, ProjectRequest.id != request.id).order_by(ProjectRequest.created_at.desc()).limit(5))
    context = GenerationContext(lineage=SourceLineage(project_id=project.id, request_id=request.id, brain_revision_id=project.current_brain_revision_id,
        plan_id=proposal.id, version_id=project.current_version_id), approved_brief=request.text, brain_json=brain.model_dump_json(),
        approved_plan_json=plan.model_dump_json(), requirements=tuple(x.encode()[:2000].decode(errors="ignore") for x in plan.scope),
        architecture="Next.js/React/TypeScript, trusted next-web-v1 scaffold. Browser-only state; no external database, network, packages, backend or production release. "+brain.architecture.overview.text[:6000],
        design_constraints=tuple(x.text[:500] for x in brain.constraints[:16]), relevant_history=tuple(x.text[:500] for x in history), base_source=source, repair_evidence=())
    return context


def queue(database: Database, settings: Settings, owner: UUID, project_id: UUID, body: StartBuild, key: str, auth_id: UUID | None = None, retry_id: UUID | None = None) -> RunRecord:
    if not settings.real_execution_enabled: raise ApplicationError("EXECUTION_UNAVAILABLE")
    with database.session() as session, session.begin():
        lock_owner(session, owner)
        project = owned_project(session, owner, project_id, lock=True)
        route = f"/v1/projects/{project_id}/builds" + (f"/{retry_id}/retry" if retry_id else "")
        receipt, replay = reserve(session, owner, route, key, body.model_dump(mode="json"), now())
        if replay: return replay
        assert receipt is not None
        proposal = session.scalar(select(PlanningProposal).where(PlanningProposal.project_id == project_id, PlanningProposal.id == body.proposal_id, PlanningProposal.user_id == owner))
        if proposal is None: raise ApplicationError("NOT_FOUND")
        if not current(session, project, proposal.context): raise ApplicationError("PLANNING_STALE_CONTEXT")
        if session.scalar(select(PlanReview.id).where(PlanReview.proposal_id == proposal.id)) is None: raise ApplicationError("PLAN_REVIEW_REQUIRED")
        if session.scalar(select(ExecutionJob.id).where(ExecutionJob.project_id == project_id, ExecutionJob.state == "done", ExecutionJob.container_name.is_not(None))): raise ApplicationError("CLEANUP_PENDING")
        available(session, project, proposal.brain_revision_id, proposal.version_id)
        prior = session.get(BuildRun, retry_id) if retry_id else None
        if retry_id and (prior is None or prior.project_id != project_id or prior.mode != "real" or prior.status != "failed"): raise ApplicationError("RUN_NOT_RETRYABLE")
        context = assemble(session, project, proposal)
        reject_secrets(settings, context.model_dump_json())
        run = BuildRun(id=uuid4(), project_id=project_id, request_id=proposal.request_id, input_brain_revision_id=proposal.brain_revision_id,
            base_version_id=proposal.version_id, retry_of_run_id=retry_id, attempt=prior.attempt+1 if prior else 1,
            mode="real", status="queued", scenario_id="next-web-v1", scenario_version=1, step_cursor=0, created_at=now())
        session.add(run); session.flush()
        session.add(ExecutionJob(id=uuid4(), project_id=project_id, user_id=owner, run_id=run.id, plan_id=proposal.id, auth_session_id=auth_id,
            state="queued", phase="context_resolution", context=context.model_dump(mode="json"), bases=fingerprint(session, project),
            epoch=0, cancel_requested=False, repairs=0, reserved_tokens=0, created_at=now(), deadline_at=now()+timedelta(seconds=settings.build_timeout_seconds)))
        project.lifecycle = "understanding"
        project.status_event_sequence = emit(session, project, run, "queued", provenance="user_requested")
        session.flush()
        result = RunRecord.model_validate(run)
        receipt.response_status, receipt.response_body = 202, result.model_dump(mode="json")
        return result


def forbidden(settings: Settings) -> tuple[str, ...]:
    values = [v.get_secret_value() for v in (settings.openai_api_key, settings.dev_api_token, settings.auth_gateway_token, settings.session_encryption_key, settings.oidc_client_secret) if v and len(v.get_secret_value()) >= 8]
    values.append(settings.database_url)
    return tuple(values)


def reject_secrets(settings: Settings, value: str) -> None:
    if any(v in value for v in forbidden(settings)): raise ApplicationError("SOURCE_SECRET_REJECTED")


def job_lock(session: Session, job_id: UUID) -> tuple[Project, ExecutionJob, BuildRun]:
    project_id = session.scalar(select(ExecutionJob.project_id).where(ExecutionJob.id == job_id))
    if project_id is None: raise ApplicationError("NOT_FOUND")
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    job = session.scalar(select(ExecutionJob).where(ExecutionJob.id == job_id).with_for_update())
    assert project is not None and job is not None
    run = session.get(BuildRun, job.run_id)
    assert run is not None
    return project, job, run


def validate_lease(session: Session, settings: Settings, project: Project, job: ExecutionJob, token: UUID) -> None:
    if job.state != "leased" or job.lease_token != token or job.lease_until is None or job.lease_until <= now(): raise ApplicationError("LEASE_LOST")
    if job.cancel_requested: raise ApplicationError("BUILD_CANCELED")
    if job.deadline_at <= now(): raise ApplicationError("BUILD_TIMEOUT")
    if project.archived_at or job.bases != fingerprint(session, project): raise ApplicationError("STALE_RUN_CONTEXT")
    if project.owner_user_id != job.user_id: raise ApplicationError("NOT_FOUND")
    if job.auth_session_id:
        auth = session.get(AuthSession, job.auth_session_id)
        if auth is None or auth.user_id != job.user_id or auth.revoked_at or auth.expires_at <= now() or auth.last_seen_at+timedelta(seconds=settings.session_idle_seconds) <= now(): raise ApplicationError("AUTHENTICATION_REQUIRED")


def claim(database: Database, settings: Settings) -> tuple[UUID, UUID] | None:
    with database.session() as session, session.begin():
        # Global concurrency boundary survives multiple worker processes.
        session.execute(text("SELECT pg_advisory_xact_lock(62002602)"))
        count = session.scalar(select(func.count()).select_from(ExecutionJob).where(or_((ExecutionJob.state == "leased") & (ExecutionJob.lease_until > now()), ExecutionJob.container_name.is_not(None)))) or 0
        if count >= settings.build_concurrency: return None
        identifier = session.scalar(select(ExecutionJob.id).where(ExecutionJob.state == "queued").order_by(ExecutionJob.created_at).limit(1))
        if identifier is None: return None
        project, job, run = job_lock(session, identifier)
        if job.state != "queued": return None
        token = uuid4()
        job.state, job.lease_token, job.epoch, job.lease_until = "leased", token, job.epoch+1, now()+timedelta(seconds=LEASE_SECONDS)
        run.status, run.started_at, run.phase = "running", run.started_at or now(), "building"
        try: validate_lease(session, settings, project, job, token)
        except ApplicationError as error:
            terminal(session, project, job, run, error.code)
            return None
        project.lifecycle = "building"
        project.status_event_sequence = emit(session, project, run, "context_resolution")
        return identifier, token


def heartbeat(database: Database, settings: Settings, identifier: UUID, token: UUID) -> bool:
    with database.session() as session, session.begin():
        project, job, run = job_lock(session, identifier)
        try: validate_lease(session, settings, project, job, token)
        except ApplicationError: return False
        job.lease_until = now()+timedelta(seconds=LEASE_SECONDS)
        run.last_heartbeat_at = now()
        return True


def terminal(session: Session, project: Project, job: ExecutionJob, run: BuildRun, error: str) -> None:
    if run.status not in ("queued", "running"): return
    run.status = "canceled" if error == "BUILD_CANCELED" else "failed"
    run.finished_at, run.error_code = now(), error
    job.state, job.lease_token, job.lease_until = "done", None, None
    project.lifecycle = "live" if project.current_version_id else "error"
    project.status_event_sequence = emit(session, project, run, run.status, failed=True)


def fail(database: Database, identifier: UUID, token: UUID, error: str) -> None:
    with database.session() as session, session.begin():
        project, job, run = job_lock(session, identifier)
        if job.lease_token == token:
            terminal(session, project, job, run, "BUILD_CANCELED" if job.cancel_requested else "BUILD_TIMEOUT" if job.deadline_at<=now() else error)


def detail(database: Database, owner: UUID, project_id: UUID, run_id: UUID) -> BuildDetail:
    with database.session(snapshot=True) as session:
        owned_project(session, owner, project_id)
        job = session.scalar(select(ExecutionJob).where(ExecutionJob.project_id == project_id, ExecutionJob.run_id == run_id))
        if job is None: raise ApplicationError("NOT_FOUND")
        run = session.get(BuildRun, run_id)
        assert run is not None
        candidates = session.scalars(select(SourceCandidate).where(SourceCandidate.job_id == job.id).order_by(SourceCandidate.attempt)).all()
        evidence = session.scalars(select(VerificationEvidence).where(VerificationEvidence.candidate_id.in_([c.id for c in candidates])).order_by(VerificationEvidence.created_at)).all()
        observed_at, progress_sequence = session.execute(select(func.max(BuildEvent.occurred_at), func.max(BuildEvent.sequence)).where(BuildEvent.project_id == project_id, BuildEvent.run_id == run_id, BuildEvent.mode == "real")).one()
        return BuildDetail(run=RunRecord.model_validate(run), phase=job.phase, cancel_requested=job.cancel_requested, repair_attempts=job.repairs,
            candidates=[CandidateMetadata(id=c.id, attempt=c.attempt, digest=c.digest, parent_digest=c.parent_digest,
                files=[{"path":f.path,"sha256":f.sha256,"bytes":len(f.content.encode())} for f in SourceArtifact.model_validate_json(json.dumps(c.source)).files], created_at=c.created_at) for c in candidates],
            evidence=[CommandEvidence.model_validate(e.content) for e in evidence],
            current_candidate_evidence=[CommandEvidence.model_validate(e.content) for e in evidence if candidates and e.candidate_id == candidates[-1].id],
            progress_updated_at=observed_at or run.created_at, progress_sequence=progress_sequence or 0)


def cancel(database: Database, owner: UUID, project_id: UUID, run_id: UUID) -> RunRecord:
    with database.session() as session, session.begin():
        project = owned_project(session, owner, project_id, lock=True)
        job = session.scalar(select(ExecutionJob).where(ExecutionJob.project_id == project_id, ExecutionJob.run_id == run_id).with_for_update())
        if job is None: raise ApplicationError("NOT_FOUND")
        run = session.get(BuildRun, job.run_id)
        assert run is not None
        if job.state != "done":
            job.cancel_requested = True
            terminal(session, project, job, run, "BUILD_CANCELED")
        session.flush()
        return RunRecord.model_validate(run)


def publish(database: Database, settings: Settings, identifier: UUID, token: UUID, candidate_id: UUID) -> bool:
    with database.session() as session, session.begin():
        seed = session.get(ExecutionJob, identifier)
        if seed is None: raise ApplicationError("NOT_FOUND")
        lock_owner(session, seed.user_id)
        if seed.auth_session_id: session.get(AuthSession,seed.auth_session_id,with_for_update=True)
        project, job, run = job_lock(session, identifier)
        validate_lease(session, settings, project, job, token)
        candidate = session.scalar(select(SourceCandidate).where(SourceCandidate.project_id == project.id, SourceCandidate.job_id == job.id, SourceCandidate.id == candidate_id))
        if candidate is None: raise ApplicationError("NOT_FOUND")
        source = SourceArtifact.model_validate_json(json.dumps(candidate.source)); validate_artifact(source)
        if source.lineage != GenerationContext.model_validate_json(json.dumps(job.context)).lineage or candidate.digest != source.digest: raise ApplicationError("STALE_RUN_CONTEXT")
        evidence = session.scalars(select(VerificationEvidence).where(VerificationEvidence.candidate_id == candidate_id)).all()
        passed = {e.phase for e in evidence if CommandEvidence.model_validate(e.content).exit_code == 0 and e.content["image_id"] == settings.sandbox_image_id}
        required = {"materialization","install","typecheck","build","verification"}
        if any(f.path.startswith('tests/') for f in source.files): required.add('test')
        if not required <= passed or not job.container_name: raise ApplicationError("VERIFICATION_REQUIRED")
        brain_id, version_id = uuid4(), uuid4()
        preview_id = job.preview_id
        if preview_id is None or job.preview_key is None: raise ApplicationError("VERIFICATION_REQUIRED")
        capability = job.preview_key
        expires = now()+timedelta(seconds=settings.preview_ttl_seconds)
        descriptor = {"kind":"isolated","preview_id":str(preview_id),"url":f"{settings.preview_origin}/p/{preview_id}/{capability}/", "source_digest":source.digest,"expires_at":expires.isoformat()}
        sequence = emit(session, project, run, "publication", candidate=candidate_id, provenance="published")
        brain: BrainContent = read_revision(session, project).content.model_copy(deep=True)
        for stage in ("model_proposed", "generated", "verified", "published"):
            provenance = Provenance(source=stage, run_id=run.id, candidate_id=candidate_id, source_digest=source.digest, plan_id=job.plan_id, request_id=run.request_id, event_sequence=sequence)
            brain.design_decisions.append(DesignDecision(decision_id=f"{stage}-{run.id}", choice=f"{stage}: next-web-v1 source {source.digest}.",
                reason="Recorded source and execution evidence. Verification covers recipe commands and runtime health; user acceptance criteria require review.", provenance=provenance))
        brain.history.request_ids = list(dict.fromkeys([*brain.history.request_ids,run.request_id]))
        brain.history.version_ids.append(version_id); brain.history.event_sequences.append(sequence)
        number = (session.scalar(select(func.max(ProjectVersion.number)).where(ProjectVersion.project_id == project.id)) or 0)+1
        revision = (session.scalar(select(func.max(BrainRevision.revision)).where(BrainRevision.project_id == project.id)) or 0)+1
        session.add(BrainRevision(id=brain_id, project_id=project.id, revision=revision, schema_version=1, source_request_id=run.request_id, source_run_id=run.id, content=BrainContent.model_validate(brain.model_dump()).model_dump(mode="json"), created_at=now()))
        session.add(ProjectVersion(id=version_id, project_id=project.id, number=number, run_id=run.id, brain_revision_id=brain_id, mode="real", summary="Verified Next.js preview; no production deployment.",preview_descriptor=descriptor,created_at=now()))
        session.add(IsolatedPreview(id=preview_id, project_id=project.id, candidate_id=candidate_id, version_id=version_id, container_name=job.container_name, capability_hash=digest(capability), state="ready",expires_at=expires,created_at=now()))
        project.current_brain_revision_id, project.current_version_id, project.lifecycle = brain_id, version_id, "live"
        run.status, run.finished_at = "succeeded", now()
        job.state, job.phase, job.container_name, job.lease_token, job.lease_until = "done", "preview_ready", None, None, None
        project.status_event_sequence = emit(session, project, run, "preview_ready", candidate=candidate_id, provenance="verified")
        session.flush()
        return True
