from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI

from f01.api.errors import register_error_handlers
from f01.api.v1.plan import router as planning_router
from f01.api.v1.projects import router as projects_router
from f01.config import Settings, get_settings
from f01.db.session import Database
from f01.execution.runner import SimulationRunner
from f01.api.v1.auth import router as auth_router
from f01.application.identity import OIDCVerifier
from f01.api.v1.context_plans import router as context_router
from f01.application.usage import DevelopmentBudget


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        configured = settings or get_settings()
        database = Database(configured.database_url)
        _app.state.database = database
        _app.state.oidc_verifier = OIDCVerifier(configured)
        stop = asyncio.Event()
        async def simulate() -> None:
            runner = SimulationRunner(database, interval_seconds=configured.simulation_tick_ms / 1000)
            while not stop.is_set():
                try:
                    await asyncio.to_thread(runner.tick)
                except Exception:
                    logging.getLogger("f01.simulation").warning("Simulation tick unavailable; persisted state will be retried.")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=configured.simulation_tick_ms / 1000)
                except TimeoutError:
                    pass
        task = asyncio.create_task(simulate()) if configured.simulation_runner_enabled else None
        try:
            yield
        finally:
            stop.set()
            if task is not None:
                await task
            database.close()

    app = FastAPI(title="F01 API", version="0.1.0", lifespan=lifespan)
    app.state.development_planning_budget = DevelopmentBudget()
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    register_error_handlers(app)
    app.include_router(planning_router)
    app.include_router(projects_router)
    app.include_router(auth_router)
    app.include_router(context_router)

    @app.get("/v1/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    return app


app = create_app()
