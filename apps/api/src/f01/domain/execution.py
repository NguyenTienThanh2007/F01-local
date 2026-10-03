"""Application-owned execution contracts; provider and Docker wire types stay outside."""
from typing import Literal
from uuid import UUID
from pydantic import Field
from f01.domain.projects import Contract, RunRecord
from f01.domain.types import UtcDateTime


class StartBuild(Contract):
    proposal_id: UUID


class Diagnostic(Contract):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,79}$")
    path: str | None = Field(default=None, max_length=240)
    line: int | None = Field(default=None, ge=1, le=100000)


class CommandEvidence(Contract):
    phase: Literal["materialization", "install", "typecheck", "build", "test", "verification"]
    argv: list[str] = Field(max_length=24)
    exit_code: int = Field(ge=0, le=255)
    duration_ms: int = Field(ge=0, le=1200000)
    diagnostics: list[Diagnostic] = Field(max_length=16)
    image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class CandidateMetadata(Contract):
    id: UUID
    attempt: int
    digest: str
    parent_digest: str | None
    files: list[dict[str, str | int]]
    created_at: UtcDateTime


class BuildDetail(Contract):
    run: RunRecord
    phase: str
    cancel_requested: bool
    repair_attempts: int
    candidates: list[CandidateMetadata]
    evidence: list[CommandEvidence]


class BuildList(Contract):
    items: list[BuildDetail]
