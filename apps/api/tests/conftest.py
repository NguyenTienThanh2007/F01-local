import pytest
from pydantic import SecretStr

from f01.config import Settings
from f01.domain.planning import ProjectPlan


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://127.0.0.1/test",
        dev_api_token=SecretStr("development-test-token-" + "x" * 32),
        openai_api_key=SecretStr("synthetic-provider-credential"),
        planning_provider="openai",
        openai_model="gpt-4.1-mini",
        planning_timeout_seconds=1.0,
        simulation_runner_enabled=False,
        _env_file=None,
    )


@pytest.fixture
def project_plan() -> ProjectPlan:
    return ProjectPlan.model_validate(
        {
            "project_title": "Harbor CRM",
            "product_summary": "Manage a small real estate agency's leads and sales pipeline.",
            "target_users": ["Real estate agents", "Agency managers"],
            "core_features": [
                {"name": "Authentication", "description": "Sign in and manage access."},
                {
                    "name": "Leads",
                    "description": "Record prospects and follow-up notes.",
                },
            ],
            "recommended_stack": {
                "frontend": "Next.js, React, TypeScript, Tailwind CSS",
                "backend": "FastAPI, Python",
                "database": "PostgreSQL",
                "rationale": "A maintainable web stack with relational data and clear API boundaries.",
            },
            "implementation_milestones": [
                {
                    "title": "Foundation",
                    "deliverables": ["Project scaffold", "Identity boundary"],
                },
                {
                    "title": "CRM workflows",
                    "deliverables": ["Lead records", "Pipeline views"],
                },
            ],
        }
    )
