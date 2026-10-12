"""Browser command acceptance only; no Docker or generated code executes here.

Reuse the cryptographic OIDC issuer and controlled planning transport. Real-mode
command reservation is injected only into this disposable test application,
as in persistence tests. This is never a sandbox acceptance report or runtime.
"""
from f01.config import get_settings
from tests.phase2a_browser_fixture import app, settings

if settings.app_env != "test" or settings.simulation_runner_enabled:
    raise RuntimeError("UX0 fixture requires explicit test mode with no simulator.")

configured = settings.model_copy(update={
    "execution_mode": "real",
    "real_execution_enabled": True,
    "sandbox_image_id": "sha256:" + "a" * 64,
    "planning_requests_per_minute": 30,
    "planning_daily_token_budget": 10000000,
})
app.dependency_overrides[get_settings] = lambda: configured
