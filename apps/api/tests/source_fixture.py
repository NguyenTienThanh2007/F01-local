from uuid import UUID

from f01.domain.brain import initial_brain
from f01.domain.context_planning import ContextPlan
from f01.domain.planning import ProjectPlan
from f01.domain.source import GenerationContext, PutFile, SourceLineage, SourceProposal


def lineage(version: bool = False) -> SourceLineage:
    return SourceLineage(project_id=UUID(int=1), request_id=UUID(int=2), brain_revision_id=UUID(int=3),
                         plan_id=UUID(int=4), version_id=UUID(int=5) if version else None)


def initial_proposal() -> SourceProposal:
    return SourceProposal(schema_version=1, recipe="next-web-v1", base_digest=None, edits=(
        PutFile(operation="put", path="app/layout.tsx", prior_sha256=None,
                content="export default function Layout({children}) { return <html><body>{children}</body></html>; }\n"),
        PutFile(operation="put", path="app/page.tsx", prior_sha256=None,
                content="export default function Page() { return <main>Hello</main>; }\n"),
    ))


def generation_context(plan: ProjectPlan) -> GenerationContext:
    return GenerationContext(lineage=lineage(), approved_brief="Build a small browser dashboard.",
        brain_json=initial_brain(UUID(int=2), "Build a small browser dashboard.").model_dump_json(),
        approved_plan_json=ContextPlan(plan=plan, scope=["Dashboard"], assumptions=["Browser only"],
            acceptance_criteria=["Show dashboard"], out_of_scope=["Deployment"]).model_dump_json(),
        requirements=("Show dashboard",), architecture="Next.js / React / TypeScript browser application",
        design_constraints=("Readable keyboard navigation",), relevant_history=(), base_source=None, repair_evidence=())
