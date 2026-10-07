from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def scoped_fk(column: str, target: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["project_id", column],
        [f"{target}.project_id", f"{target}.id"],
        name=f"fk_{column}_{target}",
        deferrable=True,
        initially="DEFERRED",
        use_alter=True,
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("identity_issuer", "identity_subject"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    identity_issuer: Mapped[str] = mapped_column(String(100))
    identity_subject: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("id", "owner_user_id"),
        ForeignKeyConstraint(
            ["id", "current_brain_revision_id"],
            ["brain_revisions.project_id", "brain_revisions.id"],
            name="fk_project_current_brain",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["id", "current_version_id"],
            ["project_versions.project_id", "project_versions.id"],
            name="fk_project_current_version",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 100", name="title"),
        CheckConstraint(
            "lifecycle IN ('idle','understanding','planning','building','verifying','deploying','live','error')",
            name="lifecycle",
        ),
        CheckConstraint(
            "metadata_version > 0 AND event_sequence >= 0 AND status_event_sequence >= 0 AND status_event_sequence <= event_sequence",
            name="counters",
        ),
        Index(
            "ix_projects_owner_listing",
            "owner_user_id",
            "archived_at",
            "updated_at",
            "id",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(100))
    lifecycle: Mapped[str] = mapped_column(String(20))
    current_brain_revision_id: Mapped[UUID]
    current_version_id: Mapped[UUID | None]
    metadata_version: Mapped[int] = mapped_column(Integer, default=1)
    event_sequence: Mapped[int] = mapped_column(Integer, default=0)
    status_event_sequence: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectRequest(Base):
    __tablename__ = "project_requests"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        ForeignKeyConstraint(
            ["project_id", "created_by"],
            ["projects.id", "projects.owner_user_id"],
            name="fk_request_owner",
        ),
        scoped_fk("base_brain_revision_id", "brain_revisions"),
        scoped_fk("base_version_id", "project_versions"),
        CheckConstraint(
            "(kind = 'initial' AND base_brain_revision_id IS NULL AND base_version_id IS NULL) OR (kind = 'change' AND base_brain_revision_id IS NOT NULL)",
            name="kind_and_base",
        ),
        CheckConstraint("length(btrim(text)) BETWEEN 20 AND 10000", name="text"),
        Index("ix_requests_history", "project_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    base_brain_revision_id: Mapped[UUID | None]
    base_version_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BrainRevision(Base):
    __tablename__ = "brain_revisions"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "revision"),
        UniqueConstraint("source_run_id"),
        scoped_fk("source_request_id", "project_requests"),
        scoped_fk("source_run_id", "build_runs"),
        CheckConstraint(
            "revision > 0 AND schema_version > 0 AND jsonb_typeof(content) = 'object'",
            name="schema",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    revision: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer)
    source_request_id: Mapped[UUID]
    source_run_id: Mapped[UUID | None]
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BuildRun(Base):
    __tablename__ = "build_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        scoped_fk("request_id", "project_requests"),
        scoped_fk("input_brain_revision_id", "brain_revisions"),
        scoped_fk("base_version_id", "project_versions"),
        scoped_fk("retry_of_run_id", "build_runs"),
        CheckConstraint("mode IN ('simulated','real')", name="mode"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','canceled')",
            name="status",
        ),
        CheckConstraint(
            "phase IS NULL OR phase IN ('understanding','planning','building','verifying','deploying')",
            name="phase",
        ),
        CheckConstraint(
            "attempt > 0 AND scenario_version > 0 AND step_cursor >= 0", name="counters"
        ),
        CheckConstraint(
            "(status = 'queued' AND phase IS NULL AND started_at IS NULL AND finished_at IS NULL) OR (status = 'running' AND phase IS NOT NULL AND started_at IS NOT NULL AND finished_at IS NULL) OR (status IN ('succeeded','failed','canceled') AND finished_at IS NOT NULL)",
            name="timing",
        ),
        Index(
            "uq_runs_one_active",
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running')"),
        ),
        Index("ix_runs_history", "project_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    request_id: Mapped[UUID]
    input_brain_revision_id: Mapped[UUID]
    base_version_id: Mapped[UUID | None]
    retry_of_run_id: Mapped[UUID | None]
    attempt: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    phase: Mapped[str | None] = mapped_column(String(20))
    scenario_id: Mapped[str] = mapped_column(String(100))
    scenario_version: Mapped[int] = mapped_column(Integer)
    step_cursor: Mapped[int] = mapped_column(Integer, default=0)
    next_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BuildEvent(Base):
    __tablename__ = "build_events"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "sequence"),
        UniqueConstraint("project_id", "deduplication_key"),
        scoped_fk("run_id", "build_runs"),
        scoped_fk("request_id", "project_requests"),
        CheckConstraint(
            "sequence > 0 AND jsonb_typeof(payload) = 'object'", name="payload"
        ),
        CheckConstraint("severity IN ('info','warning','error')", name="severity"),
        CheckConstraint("mode IS NULL OR mode IN ('simulated','real')", name="mode"),
        CheckConstraint(
            "phase IS NULL OR phase IN ('understanding','planning','building','verifying','deploying')",
            name="phase",
        ),
        Index("ix_events_run_sequence", "run_id", "sequence"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    run_id: Mapped[UUID | None]
    request_id: Mapped[UUID | None]
    sequence: Mapped[int] = mapped_column(Integer)
    deduplication_key: Mapped[str | None] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(100))
    phase: Mapped[str | None] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(1000))
    mode: Mapped[str | None] = mapped_column(String(20))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectVersion(Base):
    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "number"),
        UniqueConstraint("run_id"),
        scoped_fk("run_id", "build_runs"),
        scoped_fk("brain_revision_id", "brain_revisions"),
        CheckConstraint(
            "number > 0 AND mode IN ('simulated','real') AND jsonb_typeof(preview_descriptor) = 'object'",
            name="output",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    number: Mapped[int] = mapped_column(Integer)
    run_id: Mapped[UUID]
    brain_revision_id: Mapped[UUID]
    mode: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(String(1000))
    preview_descriptor: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DeploymentRecord(Base):
    __tablename__ = "deployment_records"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("run_id"),
        scoped_fk("run_id", "build_runs"),
        scoped_fk("version_id", "project_versions"),
        CheckConstraint(
            "mode = 'simulated' AND target = 'internal_fixture' AND external_url IS NULL",
            name="simulated",
        ),
        CheckConstraint("status IN ('pending','succeeded','failed')", name="status"),
        Index("ix_deployments_version", "version_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    version_id: Mapped[UUID]
    run_id: Mapped[UUID]
    mode: Mapped[str] = mapped_column(String(20))
    target: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    external_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "method", "route_scope", "key"),
        CheckConstraint(
            "response_status = 0 OR response_status BETWEEN 100 AND 599",
            name="response_status",
        ),
        CheckConstraint(
            "expires_at > created_at AND jsonb_typeof(response_body) = 'object'",
            name="response",
        ),
        Index("ix_idempotency_expiry", "expires_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    method: Mapped[str] = mapped_column(String(10))
    route_scope: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    issuer: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthFlow(Base):
    __tablename__ = "auth_flows"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True)
    binding_hash: Mapped[str] = mapped_column(String(64))
    nonce_hash: Mapped[str] = mapped_column(String(64))
    verifier_encrypted: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    session_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    access_hash: Mapped[str] = mapped_column(String(64))
    access_encrypted: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanningAttempt(Base):
    __tablename__ = "planning_attempts"
    __table_args__ = (UniqueConstraint("user_id", "key"), UniqueConstraint("id", "user_id", "project_id"),
        ForeignKeyConstraint(["project_id", "user_id"], ["projects.id", "projects.owner_user_id"], name="fk_attempt_owner"),
        CheckConstraint("status IN ('pending','succeeded','failed','stale','canceled','abandoned') AND reserved_tokens > 0", name="budget_status"),
        Index("ix_planning_budget", "user_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    context: Mapped[dict[str, object]] = mapped_column(JSONB)
    reserved_tokens: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanningProposal(Base):
    __tablename__ = "planning_proposals"
    __table_args__ = (UniqueConstraint("attempt_id"), UniqueConstraint("project_id", "id"), UniqueConstraint("id", "user_id"),
        ForeignKeyConstraint(["attempt_id", "user_id", "project_id"], ["planning_attempts.id", "planning_attempts.user_id", "planning_attempts.project_id"], name="fk_proposal_attempt"),
        scoped_fk("request_id", "project_requests"), scoped_fk("brain_revision_id", "brain_revisions"), scoped_fk("version_id", "project_versions"),
        ForeignKeyConstraint(["project_id", "user_id"], ["projects.id", "projects.owner_user_id"], name="fk_planning_owner"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("planning_attempts.id"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[UUID]
    brain_revision_id: Mapped[UUID]
    version_id: Mapped[UUID | None]
    kind: Mapped[str] = mapped_column(String(20))
    context: Mapped[dict[str, object]] = mapped_column(JSONB)
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlanReview(Base):
    __tablename__ = "plan_reviews"
    __table_args__ = (UniqueConstraint("proposal_id"), ForeignKeyConstraint(["proposal_id", "user_id"], ["planning_proposals.id", "planning_proposals.user_id"], name="fk_review_owner"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("planning_proposals.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExecutionJob(Base):
    __tablename__ = "execution_jobs"
    __table_args__ = (
        UniqueConstraint("run_id"), UniqueConstraint("project_id", "id"),
        scoped_fk("run_id", "build_runs"), scoped_fk("plan_id", "planning_proposals"),
        ForeignKeyConstraint(["project_id", "user_id"], ["projects.id", "projects.owner_user_id"], name="fk_execution_owner"),
        CheckConstraint("state IN ('queued','leased','done') AND epoch >= 0 AND repairs >= 0 AND reserved_tokens >= 0", name="state"),
        Index("ix_execution_queue", "state", "lease_until", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    run_id: Mapped[UUID]
    plan_id: Mapped[UUID]
    auth_session_id: Mapped[UUID | None] = mapped_column(ForeignKey("auth_sessions.id"))
    state: Mapped[str] = mapped_column(String(20))
    phase: Mapped[str] = mapped_column(String(40))
    context: Mapped[dict[str, object]] = mapped_column(JSONB)
    bases: Mapped[dict[str, object]] = mapped_column(JSONB)
    epoch: Mapped[int] = mapped_column(Integer)
    lease_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool]
    repairs: Mapped[int] = mapped_column(Integer)
    reserved_tokens: Mapped[int] = mapped_column(Integer)
    preview_id: Mapped[UUID | None]
    preview_key: Mapped[str | None] = mapped_column(String(100))
    container_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceCandidate(Base):
    __tablename__ = "source_candidates"
    __table_args__ = (
        UniqueConstraint("project_id", "id"), UniqueConstraint("job_id", "attempt"),
        scoped_fk("job_id", "execution_jobs"),
        CheckConstraint("attempt >= 0 AND length(digest) = 64 AND octet_length(source::text) <= 1048576", name="bounds"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    job_id: Mapped[UUID]
    attempt: Mapped[int] = mapped_column(Integer)
    digest: Mapped[str] = mapped_column(String(64))
    parent_digest: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VerificationEvidence(Base):
    __tablename__ = "verification_evidence"
    __table_args__ = (
        UniqueConstraint("project_id", "id"), UniqueConstraint("candidate_id", "phase"),
        scoped_fk("candidate_id", "source_candidates"),
        CheckConstraint("octet_length(content::text) <= 8192", name="bounds"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    candidate_id: Mapped[UUID]
    phase: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IsolatedPreview(Base):
    __tablename__ = "isolated_previews"
    __table_args__ = (
        UniqueConstraint("project_id", "id"), UniqueConstraint("version_id"), UniqueConstraint("container_name"),
        scoped_fk("candidate_id", "source_candidates"), scoped_fk("version_id", "project_versions"),
        CheckConstraint("state IN ('ready','expired','cleanup_pending','removed')", name="state"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    candidate_id: Mapped[UUID]
    version_id: Mapped[UUID]
    container_name: Mapped[str] = mapped_column(String(100))
    capability_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReleaseConfiguration(Base):
    __tablename__ = 'release_configurations'
    __table_args__ = (UniqueConstraint('project_id', 'id'), UniqueConstraint('project_id', 'digest'),
        CheckConstraint("profile = 'next-static-v1' AND provider = 'vercel' AND length(digest) = 64", name='profile'),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('projects.id'))
    profile: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(20))
    provider_project_id: Mapped[str] = mapped_column(String(100), unique=True)
    provider_team_id: Mapped[str | None] = mapped_column(String(100))
    public_url: Mapped[str] = mapped_column(String(250), unique=True)
    digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtifactPreparation(Base):
    __tablename__ = 'artifact_preparations'
    __table_args__ = (UniqueConstraint('project_id', 'id'), UniqueConstraint('project_id', 'intent_hash'),
        scoped_fk('version_id', 'project_versions'), scoped_fk('brain_revision_id', 'brain_revisions'), scoped_fk('configuration_id', 'release_configurations'),
        scoped_fk('artifact_id', 'release_artifacts'),
        CheckConstraint("state IN ('queued','packaging','succeeded','failed','canceled') AND epoch >= 0", name='state'),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('projects.id'))
    version_id: Mapped[UUID]
    brain_revision_id: Mapped[UUID]
    configuration_id: Mapped[UUID]
    intent_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20))
    artifact_id: Mapped[UUID | None]
    error_code: Mapped[str | None] = mapped_column(String(100))
    epoch: Mapped[int] = mapped_column(Integer)
    lease_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    container_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReleaseArtifact(Base):
    __tablename__ = 'release_artifacts'
    __table_args__ = (UniqueConstraint('project_id', 'id'), UniqueConstraint('preparation_id'),
        scoped_fk('preparation_id', 'artifact_preparations'), scoped_fk('version_id', 'project_versions'), scoped_fk('brain_revision_id', 'brain_revisions'),
        scoped_fk('configuration_id', 'release_configurations'), scoped_fk('candidate_id', 'source_candidates'),
        CheckConstraint("length(digest) = 64 AND octet_length(package::text) <= 24000000 AND octet_length(manifest::text) <= 131072", name='bounds'),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('projects.id'))
    preparation_id: Mapped[UUID]
    version_id: Mapped[UUID]
    brain_revision_id: Mapped[UUID]
    configuration_id: Mapped[UUID]
    candidate_id: Mapped[UUID]
    digest: Mapped[str] = mapped_column(String(64))
    package: Mapped[dict[str, object]] = mapped_column(JSONB)
    manifest: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReleaseIntent(Base):
    __tablename__ = 'release_intents'
    __table_args__ = (UniqueConstraint('project_id', 'id'), UniqueConstraint('project_id', 'intent_hash'),
        scoped_fk('artifact_id', 'release_artifacts'), scoped_fk('configuration_id', 'release_configurations'),
        scoped_fk('version_id', 'project_versions'), scoped_fk('brain_revision_id', 'brain_revisions'), scoped_fk('previous_release_id', 'release_intents'),
        ForeignKeyConstraint(['project_id', 'user_id'], ['projects.id', 'projects.owner_user_id'], name='fk_release_owner'),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('projects.id'))
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    auth_session_id: Mapped[UUID | None] = mapped_column(ForeignKey('auth_sessions.id'))
    artifact_id: Mapped[UUID]
    configuration_id: Mapped[UUID]
    version_id: Mapped[UUID]
    brain_revision_id: Mapped[UUID]
    previous_release_id: Mapped[UUID | None]
    target_generation: Mapped[int] = mapped_column(Integer)
    intent_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReleaseOperation(Base):
    __tablename__ = 'release_operations'
    __table_args__ = (UniqueConstraint('project_id', 'id'), UniqueConstraint('release_id'), scoped_fk('release_id', 'release_intents'),
        CheckConstraint("state IN ('queued','staging','checking','promoting','verifying','reconciling','restoring','succeeded','failed','canceled') AND epoch >= 0 AND attempts >= 0", name='state'),
        Index('uq_release_one_active', 'project_id', unique=True, postgresql_where=text("state NOT IN ('succeeded','failed','canceled')")),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('projects.id'))
    release_id: Mapped[UUID]
    state: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(30))
    deployment_id: Mapped[str | None] = mapped_column(String(100))
    deployment_url: Mapped[str | None] = mapped_column(String(250))
    public_url: Mapped[str | None] = mapped_column(String(250))
    error_code: Mapped[str | None] = mapped_column(String(100))
    cancel_requested: Mapped[bool]
    epoch: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer)
    lease_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReleaseObservation(Base):
    __tablename__ = 'release_observations'
    __table_args__ = (UniqueConstraint('project_id', 'id'), scoped_fk('operation_id', 'release_operations'),
        CheckConstraint('octet_length(content::text) <= 8192', name='bounds'),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('projects.id'))
    operation_id: Mapped[UUID]
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductionTarget(Base):
    __tablename__ = 'production_targets'
    __table_args__ = (UniqueConstraint('project_id', 'id'), UniqueConstraint('project_id'),
        scoped_fk('configuration_id', 'release_configurations'), scoped_fk('current_release_id', 'release_intents'),
        CheckConstraint('generation >= 0', name='generation'),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('projects.id'))
    configuration_id: Mapped[UUID]
    current_release_id: Mapped[UUID | None]
    generation: Mapped[int] = mapped_column(Integer)
