"""Short, atomic due steps. PostgreSQL is the progress and publication authority."""
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from f01.application.projects import read_revision
from f01.application.runs import simulation_event
from f01.db.models import BrainRevision, BuildEvent, BuildRun, DeploymentRecord, Project, ProjectRequest, ProjectVersion
from f01.db.session import Database
from f01.domain.brain import BrainContent, DesignDecision, Feature, Provenance, Requirement, Statement
from f01.domain.errors import ApplicationError
from f01.domain.lifecycle import ACTIVE_STATUSES, Phase, RunStatus, lifecycle_after_terminal, transition_phase, transition_status
from f01.domain.projects import EventPayload
from f01.execution.scenarios import scenario


def utc_now() -> datetime:
    return datetime.now(UTC)


class SimulationRunner:
    def __init__(self, database: Database, *, interval_seconds: float = 1, clock: Callable[[], datetime] = utc_now) -> None:
        self.database = database
        self.interval = interval_seconds
        self.clock = clock

    def tick(self) -> int:
        now = self.clock()
        with self.database.session() as session:
            due = session.scalars(select(BuildRun.id).where(BuildRun.status.in_(ACTIVE_STATUSES),
                (BuildRun.next_step_at.is_(None)) | (BuildRun.next_step_at <= now))
                .order_by(BuildRun.next_step_at.asc().nullsfirst(), BuildRun.created_at, BuildRun.id).limit(100)).all()
        return sum(self.advance(run_id, now=now) for run_id in due)

    def advance(self, run_id: UUID, *, now: datetime | None = None) -> bool:
        now = now or self.clock()
        with self.database.session() as session, session.begin():
            session.execute(text("SET LOCAL lock_timeout = '2s'"))
            project_id = session.scalar(select(BuildRun.project_id).where(BuildRun.id == run_id))
            if project_id is None:
                return False
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            assert project is not None
            run = session.scalar(select(BuildRun).where(BuildRun.id == run_id).with_for_update())
            assert run is not None
            if run.status not in ACTIVE_STATUSES or (run.next_step_at is not None and run.next_step_at > now):
                return False
            definition = scenario(run.scenario_id, run.scenario_version)
            index = 0

            def emit(type: str, message: str, *, severity: str = "info", issue: str | None = None, resolves: str | None = None, recoverable: bool | None = None) -> int:
                nonlocal index
                payload = EventPayload(step_cursor=run.step_cursor, scenario_step=run.step_cursor, event_index=index,
                    issue_id=issue, resolves_issue_id=resolves, recoverable=recoverable)
                seq = simulation_event(session, project, run, now, type=type, message=message, severity=severity,
                    payload=payload, deduplication_key=f"{run.id}:{run.step_cursor}:{index}")
                index += 1
                return seq

            def fail(code: str, message: str) -> None:
                run.status = transition_status(cast(RunStatus, run.status), "failed")
                run.error_code = code
                run.finished_at = now
                run.next_step_at = None
                project.lifecycle = "error"
                project.status_event_sequence = emit("run.failed", message, severity="error")

            if definition is None:
                fail("SCENARIO_VERSION_UNAVAILABLE", "Simulation: the persisted scenario version is unavailable. No replacement fixture or output was published.")
            elif run.step_cursor >= len(definition.steps):
                fail("SCENARIO_CURSOR_INVALID", "Simulation: the saved fixture cursor is invalid. No output was published.")
            elif project.current_brain_revision_id != run.input_brain_revision_id or project.current_version_id != run.base_version_id:
                fail("STALE_RUN_CONTEXT", "Simulation: the frozen input context no longer matches this project. Review a new request; the successful preview is preserved.")
            else:
                try:
                    read_revision(session, project)
                except ApplicationError as error:
                    if error.code != "UNSUPPORTED_BRAIN_SCHEMA":
                        raise
                    fail(error.code, "Simulation: the frozen Brain schema is unsupported. No output was published.")
                else:
                    step = definition.steps[run.step_cursor]
                    if run.status == "queued":
                        run.status = transition_status("queued", "running")
                        run.started_at = now
                    repair_seq = None
                    if step.repair:
                        issue = f"{run.id}:sample-auth-callback"
                        prior = session.scalar(select(BuildEvent.sequence).where(BuildEvent.run_id == run.id,
                            BuildEvent.type == "verification.failed", BuildEvent.payload["issue_id"].astext == issue))
                        if prior is None:
                            fail("SCENARIO_REPAIR_INVALID", "Simulation: fixture repair has no recorded issue. No output was published.")
                        else:
                            for event in step.events:
                                repair_seq = emit(event.type, event.message, resolves=f"{run.id}:{event.resolves}", severity=event.severity)
                    if run.status == "running":
                        if run.phase != step.phase:
                            run.phase = transition_phase(cast(Phase | None, run.phase), step.phase, repair_event_sequence=repair_seq)
                            project.lifecycle = run.phase
                            project.status_event_sequence = emit("run.phase_changed", f"Simulation: {run.phase.capitalize()} fixture stage.")
                        if not step.repair:
                            for event in step.events:
                                emit(event.type, event.message, severity=event.severity,
                                    issue=f"{run.id}:{event.issue}" if event.issue else None,
                                    resolves=f"{run.id}:{event.resolves}" if event.resolves else None, recoverable=event.recoverable)
                        if step.outcome == "failure":
                            fail("SIMULATED_VERIFICATION_FAILURE", "Simulation: update needs attention. No Brain revision, version or deployment was published; the last successful preview remains available.")
                        elif step.outcome == "success":
                            self.publish(session, project, run, now, emit)
                        else:
                            run.next_step_at = now + timedelta(seconds=self.interval)
            run.step_cursor += 1
            run.last_heartbeat_at = now
            session.flush()
            return True

    def publish(self, session: Session, project: Project, run: BuildRun, now: datetime, emit: Callable[..., int]) -> None:
        content: BrainContent = read_revision(session, project).content.model_copy(deep=True)
        request = session.get(ProjectRequest, run.request_id)
        assert request is not None
        brain_id, version_id, deployment_id = (uuid4() for _ in range(3))
        number = (session.scalar(select(func.max(ProjectVersion.number)).where(ProjectVersion.project_id == project.id)) or 0) + 1
        revision = (session.scalar(select(func.max(BrainRevision.revision)).where(BrainRevision.project_id == project.id)) or 0) + 1
        fixture = "crm-v1" if "crm" in content.product.summary.text.casefold() else "generic-v1"
        previous = session.get(ProjectVersion, run.base_version_id) if run.base_version_id else None
        descriptor = previous.preview_descriptor if previous else {"kind": "fixture", "fixture_id": fixture, "fixture_revision": 1}
        evidence_seq = emit("version.created", f"Simulation: demo version {number} recorded from a bundled fixture; arbitrary requests may leave its interface unchanged.")
        emit("deployment.simulated", "Simulation: internal fixture deployment record published. No external host, URL or release exists.")
        run.status = transition_status("running", "succeeded")
        run.finished_at = now
        run.next_step_at = None
        project.lifecycle = lifecycle_after_terminal("succeeded", has_version=True)
        project.status_event_sequence = emit("run.succeeded", "Simulation: Live · Demo. A curated sample preview is available; no application was generated, tested or deployed.")
        provenance = Provenance(source="simulation", run_id=run.id, event_sequence=evidence_seq)
        if request.id not in content.history.request_ids:
            user = Provenance(source="user_request", request_id=request.id)
            requirement_id = f"request-{request.id}"
            content.product.requirements.append(Requirement(requirement_id=requirement_id, text=request.text, provenance=user,
                priority="must", assumption=True, acceptance_criteria=[Statement(text="Review this saved intent before real implementation. The simulation fixture does not verify requested behavior.", provenance=provenance)]))
            content.features.append(Feature(feature_id=f"feature-{request.id}", text=request.text, provenance=user, requirement_ids=[requirement_id], state="requested"))
            content.history.request_ids.append(request.id)
        content.design_decisions.append(DesignDecision(decision_id=f"simulation-{run.id}", choice=f"Inspect the bundled {descriptor['fixture_id']} sample.",
            reason="Deterministic demonstration only. Requested intent is preserved; no source or real verification evidence was produced.", provenance=provenance))
        session.flush()  # includes this step's events; still inside the publication transaction
        events = session.scalars(select(BuildEvent).where(BuildEvent.project_id == project.id).order_by(BuildEvent.sequence)).all()
        content.history.event_sequences = sorted(set(content.history.event_sequences + [event.sequence for event in events]))
        content.history.issue_ids = list(dict.fromkeys(content.history.issue_ids + [str(e.payload['issue_id']) for e in events if e.payload.get('issue_id')]))
        content.history.version_ids.append(version_id)
        content.history.deployment_ids.append(deployment_id)
        session.add(BrainRevision(id=brain_id, project_id=project.id, revision=revision, schema_version=1,
            source_request_id=run.request_id, source_run_id=run.id, content=BrainContent.model_validate(content.model_dump()).model_dump(mode="json"), created_at=now))
        session.add(ProjectVersion(id=version_id, project_id=project.id, number=number, run_id=run.id, brain_revision_id=brain_id,
            mode="simulated", summary="Simulation: curated fixture demonstration. Saved changes do not imply changes to sample behavior.", preview_descriptor=descriptor, created_at=now))
        session.add(DeploymentRecord(id=deployment_id, project_id=project.id, version_id=version_id, run_id=run.id,
            mode="simulated", target="internal_fixture", status="succeeded", external_url=None, created_at=now, completed_at=now))
        project.current_brain_revision_id = brain_id
        project.current_version_id = version_id
