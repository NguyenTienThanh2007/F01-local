from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from f01.domain.lifecycle import Phase


class BrainModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True
    )


class Provenance(BrainModel):
    source: Literal["user_request", "template", "simulation"]
    request_id: UUID | None = None
    fixture_ref: str | None = Field(default=None, max_length=100)
    run_id: UUID | None = None
    event_sequence: int | None = Field(default=None, gt=0, le=2147483647)

    @model_validator(mode="after")
    def has_reference(self) -> Self:
        if self.source == "user_request" and self.request_id is None:
            raise ValueError("User provenance requires a request reference.")
        if self.source == "template" and not self.fixture_ref:
            raise ValueError("Template provenance requires a template reference.")
        if self.source == "simulation" and (
            self.run_id is None or self.event_sequence is None
        ):
            raise ValueError("Simulation provenance requires run and event references.")
        return self


class Statement(BrainModel):
    text: str = Field(min_length=1, max_length=10000)
    provenance: Provenance


class Requirement(Statement):
    requirement_id: str = Field(min_length=1, max_length=100)
    priority: Literal["must", "should", "could"]
    acceptance_criteria: list[Statement] = Field(min_length=1, max_length=30)
    assumption: bool


class Product(BrainModel):
    summary: Statement
    requirements: list[Requirement] = Field(min_length=1, max_length=200)


class PlanStep(Statement):
    step_id: str = Field(min_length=1, max_length=100)
    phase: Phase
    requirement_ids: list[str]
    dependencies: list[str]
    status: Literal["proposed"] = "proposed"


class Architecture(BrainModel):
    overview: Statement
    component_relationships: list[Statement]
    rationale: Statement
    evidence: Literal["proposed", "simulated"]


class Stack(BrainModel):
    frontend: Statement
    backend: Statement
    database: Statement
    rationale: Statement


class DatabaseEntity(Statement):
    entity_id: str
    fields: list[Statement]
    relationships: list[Statement]


class DatabaseProposal(BrainModel):
    entities: list[DatabaseEntity]
    unresolved: list[Statement]


class Feature(Statement):
    feature_id: str
    requirement_ids: list[str]
    state: Literal["requested", "planned", "simulated"]


class DesignDecision(BrainModel):
    decision_id: str
    choice: str
    reason: str
    provenance: Provenance
    supersedes_decision_id: str | None = None


class BrainHistory(BrainModel):
    request_ids: list[UUID]
    issue_ids: list[str]
    event_sequences: list[int]
    version_ids: list[UUID]
    deployment_ids: list[UUID]


class BrainContent(BrainModel):
    original_request_id: UUID
    product: Product
    plan: list[PlanStep]
    architecture: Architecture
    stack: Stack
    database: DatabaseProposal
    features: list[Feature]
    design_decisions: list[DesignDecision]
    constraints: list[Statement]
    open_questions: list[Statement]
    history: BrainHistory

    @model_validator(mode="after")
    def linked_entries(self) -> Self:
        requirements = [r.requirement_id for r in self.product.requirements]
        steps = [s.step_id for s in self.plan]
        features = [f.feature_id for f in self.features]
        decisions = [d.decision_id for d in self.design_decisions]
        if any(
            len(ids) != len(set(ids))
            for ids in (requirements, steps, features, decisions)
        ):
            raise ValueError("Brain entry identifiers must be unique.")
        seen: set[str] = set()
        for step in self.plan:
            if (
                not set(step.requirement_ids) <= set(requirements)
                or not set(step.dependencies) <= seen
            ):
                raise ValueError("Plan references must resolve in dependency order.")
            seen.add(step.step_id)
        if any(not set(f.requirement_ids) <= set(requirements) for f in self.features):
            raise ValueError("Feature requirements must resolve.")
        if self.original_request_id not in self.history.request_ids:
            raise ValueError("Original request must remain in history.")
        return self


def initial_brain(request_id: UUID, brief: str) -> BrainContent:
    user = Provenance(source="user_request", request_id=request_id)
    template = Provenance(source="template", fixture_ref="phase1-initial-brain@1")

    def proposed(text: str) -> Statement:
        return Statement(text=text, provenance=template)

    phases: list[Phase] = [
        "understanding",
        "planning",
        "building",
        "verifying",
        "deploying",
    ]
    return BrainContent(
        original_request_id=request_id,
        product=Product(
            summary=Statement(text=brief, provenance=user),
            requirements=[
                Requirement(
                    requirement_id="req-001",
                    text=brief,
                    provenance=user,
                    priority="must",
                    acceptance_criteria=[
                        proposed(
                            "Review the original brief and confirm detailed acceptance criteria before real implementation."
                        )
                    ],
                    assumption=True,
                )
            ],
        ),
        plan=[
            PlanStep(
                step_id=f"step-{i + 1:03}",
                phase=phase,
                text=f"Proposed {phase} stage; demonstrations use fixture simulation only.",
                provenance=template,
                requirement_ids=["req-001"],
                dependencies=[] if i == 0 else [f"step-{i:03}"],
            )
            for i, phase in enumerate(phases)
        ],
        architecture=Architecture(
            overview=proposed(
                "Proposed web interface, API and relational data store; detailed architecture needs review."
            ),
            component_relationships=[
                proposed(
                    "Web interface communicates with an API; the API owns database access."
                )
            ],
            rationale=proposed(
                "A conventional web stack is a template assumption, not a generated architecture."
            ),
            evidence="proposed",
        ),
        stack=Stack(
            frontend=proposed("Next.js, React, TypeScript, Tailwind CSS"),
            backend=proposed("FastAPI, Python"),
            database=proposed("PostgreSQL"),
            rationale=proposed(
                "Suggested generated-project stack; independent of factory configuration and subject to review."
            ),
        ),
        database=DatabaseProposal(
            entities=[],
            unresolved=[
                proposed(
                    "Identify application entities and access rules during planning; no application database exists."
                )
            ],
        ),
        features=[
            Feature(
                feature_id="feature-001",
                text=brief,
                provenance=user,
                requirement_ids=["req-001"],
                state="requested",
            )
        ],
        design_decisions=[
            DesignDecision(
                decision_id="decision-001",
                choice="Preserve the original brief and explicit assumptions.",
                reason="Future edits need traceable context rather than replacing the original request.",
                provenance=template,
            )
        ],
        constraints=[
            proposed(
                "Phase 1 uses simulation only; no generated source, execution or deployment."
            )
        ],
        open_questions=[
            proposed(
                "Confirm target users, detailed workflows and measurable acceptance criteria."
            )
        ],
        history=BrainHistory(
            request_ids=[request_id],
            issue_ids=[],
            event_sequences=[1],
            version_ids=[],
            deployment_ids=[],
        ),
    )
