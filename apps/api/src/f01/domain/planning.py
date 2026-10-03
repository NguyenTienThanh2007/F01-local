from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class PlanModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class CoreFeature(PlanModel):
    name: Title
    description: Description


class RecommendedStack(PlanModel):
    frontend: ShortText
    backend: ShortText
    database: ShortText
    rationale: Description


class ImplementationMilestone(PlanModel):
    title: Title
    deliverables: list[ShortText] = Field(min_length=1, max_length=10)


class ProjectPlan(PlanModel):
    project_title: Title
    product_summary: Description
    target_users: list[ShortText] = Field(min_length=1, max_length=10)
    core_features: list[CoreFeature] = Field(min_length=1, max_length=16)
    recommended_stack: RecommendedStack
    implementation_milestones: list[ImplementationMilestone] = Field(
        min_length=1, max_length=12
    )
