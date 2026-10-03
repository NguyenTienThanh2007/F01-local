"""Planning proposals are typed intent; they carry no executable operations."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field
from f01.domain.planning import PlanModel, ProjectPlan, ShortText
from f01.domain.projects import Contract

class ContextPlan(PlanModel):
    plan: ProjectPlan
    scope: list[ShortText] = Field(min_length=1, max_length=16)
    assumptions: list[ShortText] = Field(max_length=10)
    acceptance_criteria: list[ShortText] = Field(min_length=1, max_length=16)
    out_of_scope: list[ShortText] = Field(max_length=10)

class PlanInput(Contract):
    kind: Literal["initial", "change"]
    request_id: UUID
    base_brain_revision_id: UUID
    base_version_id: UUID | None

class ProposalRecord(Contract):
    id: UUID
    attempt_id: UUID
    project_id: UUID
    request_id: UUID
    brain_revision_id: UUID
    version_id: UUID | None
    kind: Literal["initial", "change"]
    content: ContextPlan
    context: dict[str, object]
    provider: str
    model: str
    created_at: datetime
    current_context: bool
    reviewed: bool

class AttemptRecord(Contract):
    id: UUID
    project_id: UUID | None
    status: str
    reserved_tokens: int
    input_tokens: int | None
    output_tokens: int | None
    error_code: str | None
    created_at: datetime
    deadline_at: datetime
    proposal: ProposalRecord | None = None

class ProposalList(Contract):
    items: list[ProposalRecord]

class PlanningResult(PlanModel):
    content: ContextPlan
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)

class UsageView(Contract):
    requests_used: int
    requests_per_day: int
    requests_per_minute: int
    tokens_reserved: int
    daily_token_budget: int
    input_token_limit: int
    output_token_limit: int
    resets_at: datetime
