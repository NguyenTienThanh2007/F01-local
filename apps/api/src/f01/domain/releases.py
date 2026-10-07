"""Production contracts. No provider credentials, storage paths or executable input."""
from typing import Literal
from uuid import UUID
from pydantic import Field
from f01.domain.projects import Contract
from f01.domain.types import UtcDateTime


class PrepareRelease(Contract):
    version_id: UUID
    configuration_id: UUID
    expected_brain_revision_id: UUID


class PromoteRelease(Contract):
    artifact_id: UUID
    configuration_id: UUID
    expected_brain_revision_id: UUID
    expected_version_id: UUID
    expected_production_release_id: UUID | None
    expected_target_generation: int = Field(ge=0)


class ProductionConfiguration(Contract):
    id: UUID
    project_id: UUID
    profile: Literal['next-static-v1']
    provider: Literal['vercel']
    public_url: str
    digest: str
    created_at: UtcDateTime


class ArtifactPreparation(Contract):
    id: UUID
    project_id: UUID
    version_id: UUID
    configuration_id: UUID
    state: Literal['queued', 'packaging', 'succeeded', 'failed', 'canceled']
    artifact_id: UUID | None
    error_code: str | None
    created_at: UtcDateTime


class ReleaseArtifact(Contract):
    id: UUID
    project_id: UUID
    version_id: UUID
    brain_revision_id: UUID
    configuration_id: UUID
    candidate_id: UUID
    digest: str
    manifest: dict[str, object]
    created_at: UtcDateTime


class ReleaseDetail(Contract):
    id: UUID
    project_id: UUID
    artifact_id: UUID
    configuration_id: UUID
    version_id: UUID
    previous_release_id: UUID | None
    state: Literal['queued', 'staging', 'checking', 'promoting', 'verifying', 'reconciling', 'restoring', 'succeeded', 'failed', 'canceled']
    public_url: str | None
    deployment_url: str | None
    error_code: str | None
    cancel_requested: bool
    last_observed_at: UtcDateTime | None
    created_at: UtcDateTime


class ReleaseWorkspace(Contract):
    available: bool
    configuration: ProductionConfiguration | None
    target_generation: int
    current_release_id: UUID | None
    preparations: list[ArtifactPreparation]
    artifacts: list[ReleaseArtifact]
    releases: list[ReleaseDetail]
