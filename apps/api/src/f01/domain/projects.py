from f01.domain.types import UtcDateTime
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from f01.domain.brain import BrainContent
from f01.domain.lifecycle import Lifecycle, Phase, RunStatus

MAX_COUNTER = 2147483647


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        from_attributes=True,
        hide_input_in_errors=True,
    )


class CreateProject(Contract):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    brief: str = Field(min_length=20, max_length=10000)


class UpdateProject(Contract):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    archived: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def nonempty_patch(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError(
                "Supply a title and/or archived state; null is not an update."
            )
        return self


class ProjectSummary(Contract):
    id: UUID
    owner_user_id: UUID
    title: str
    lifecycle: Lifecycle
    current_brain_revision_id: UUID
    current_version_id: UUID | None
    metadata_version: int = Field(gt=0, le=MAX_COUNTER)
    event_sequence: int = Field(ge=0, le=MAX_COUNTER)
    status_event_sequence: int = Field(ge=0, le=MAX_COUNTER)
    last_activity_at: UtcDateTime
    archived_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ProjectCreated(Contract):
    project: ProjectSummary
    project_url: str
    request_id: UUID
    brain_revision_id: UUID
    run_id: UUID | None
    execution_mode: Literal["simulated", "real"] = "simulated"


class RequestRecord(Contract):
    id: UUID
    project_id: UUID
    created_by: UUID
    kind: Literal["initial", "change"]
    text: str
    base_brain_revision_id: UUID | None
    base_version_id: UUID | None
    created_at: UtcDateTime


class RecordChange(Contract):
    text: str = Field(min_length=20, max_length=10000)
    base_brain_revision_id: UUID
    base_version_id: UUID | None


class StartRun(Contract):
    request_id: UUID
    expected_brain_revision_id: UUID


class RetryRun(Contract):
    pass


class BrainRevisionSummary(Contract):
    id: UUID
    project_id: UUID
    revision: int = Field(gt=0, le=MAX_COUNTER)
    schema_version: int = Field(gt=0)
    source_request_id: UUID
    source_run_id: UUID | None
    created_at: UtcDateTime


class BrainRevisionRecord(BrainRevisionSummary):
    content: BrainContent


class RunRecord(Contract):
    id: UUID
    project_id: UUID
    request_id: UUID
    input_brain_revision_id: UUID
    base_version_id: UUID | None
    retry_of_run_id: UUID | None
    attempt: int = Field(gt=0, le=MAX_COUNTER)
    mode: Literal["simulated", "real"]
    status: RunStatus
    phase: Phase | None
    scenario_id: str
    scenario_version: int
    step_cursor: int
    next_step_at: UtcDateTime | None
    last_heartbeat_at: UtcDateTime | None
    error_code: str | None
    created_at: UtcDateTime
    started_at: UtcDateTime | None
    finished_at: UtcDateTime | None


class EventPayload(Contract):
    schema_version: Literal[1] = 1
    actor_user_id: UUID | None = None
    issue_id: str | None = Field(default=None, min_length=1, max_length=100)
    resolves_issue_id: str | None = Field(default=None, min_length=1, max_length=100)
    scenario_step: int | None = Field(default=None, ge=0)
    recoverable: bool | None = None
    step_cursor: int | None = Field(default=None, ge=0)
    event_index: int | None = Field(default=None, ge=0)
    execution_phase: str | None = None
    candidate_id: UUID | None = None
    evidence_id: UUID | None = None
    source_digest: str | None = None
    provenance: str | None = None


class EventRecord(Contract):
    id: UUID
    project_id: UUID
    run_id: UUID | None
    request_id: UUID | None
    sequence: int = Field(gt=0, le=MAX_COUNTER)
    type: str
    phase: Phase | None
    severity: Literal["info", "warning", "error"]
    mode: Literal["simulated", "real"] | None
    message: str
    payload: EventPayload
    occurred_at: UtcDateTime


class PreviewDescriptor(Contract):
    kind: Literal["fixture"]
    fixture_id: Literal["crm-v1", "generic-v1"]
    fixture_revision: int | None = Field(default=None, gt=0)


class RealPreviewDescriptor(Contract):
    kind: Literal["isolated"]
    preview_id: UUID
    url: str
    browser_url: str | None = None
    source_digest: str
    expires_at: UtcDateTime


class VersionRecord(Contract):
    id: UUID
    project_id: UUID
    number: int
    run_id: UUID
    brain_revision_id: UUID
    mode: Literal["simulated", "real"]
    summary: str
    preview_descriptor: PreviewDescriptor | RealPreviewDescriptor
    created_at: UtcDateTime


class DeploymentRecordView(Contract):
    id: UUID
    project_id: UUID
    version_id: UUID
    run_id: UUID
    mode: Literal["simulated", "real"]
    target: Literal["internal_fixture"]
    status: Literal["pending", "succeeded", "failed"]
    external_url: None
    created_at: UtcDateTime
    completed_at: UtcDateTime | None


class CanonicalContext(Contract):
    requests: list[RequestRecord]
    issue_events: list[EventRecord]
    versions: list[VersionRecord]
    deployments: list[DeploymentRecordView]


class BrainView(Contract):
    revision: BrainRevisionRecord
    context: CanonicalContext


class PreviewState(Contract):
    status: Literal["pending", "available"]
    descriptor: PreviewDescriptor | RealPreviewDescriptor | None
    message: str


class WorkspaceSnapshot(Contract):
    project: ProjectSummary
    current_brain: BrainRevisionRecord
    active_run: RunRecord | None
    latest_run: RunRecord | None
    current_version: VersionRecord | None
    preview: PreviewState
    recent_events: list[EventRecord]
    last_sequence: int = Field(ge=0, le=MAX_COUNTER)


class Principal(Contract):
    id: UUID
    display_name: str
    identity_mode: Literal["development", "oidc"] = "development"


class AccountProfile(Contract):
    display_name: str
    email: str | None = None
    email_verified: bool = False
    identity_mode: Literal["development", "oidc"]

class UpdateAccount(Contract):
    display_name: str = Field(min_length=1, max_length=100)

class Capabilities(Contract):
    execution_mode: Literal["simulated", "real"] = "simulated"
    real_generation: bool = False
    external_deployment: bool = False
    source_artifacts: bool = False
    simulation_runner: bool = False


class SessionView(Contract):
    principal: Principal
    capabilities: Capabilities = Field(default_factory=Capabilities)
    expires_at: UtcDateTime | None = None


class ProjectList(Contract):
    items: list[ProjectSummary]
    next_cursor: str | None


class RequestList(Contract):
    items: list[RequestRecord]
    next_cursor: str | None


class BrainRevisionList(Contract):
    items: list[BrainRevisionSummary]
    next_cursor: str | None


class EventList(Contract):
    items: list[EventRecord]
    next_cursor: str | None


class VersionList(Contract):
    items: list[VersionRecord]
    next_cursor: str | None


class RunList(Contract):
    items: list[RunRecord]
    next_cursor: str | None


class DeploymentList(Contract):
    items: list[DeploymentRecordView]
    next_cursor: str | None
