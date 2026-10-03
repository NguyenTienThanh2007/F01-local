from typing import Annotated

from fastapi import APIRouter, Depends, Request
from uuid import uuid4
import asyncio
from f01.application import planning as service
from f01.application.identity import digest
from f01.application.usage import DevelopmentBudget
from f01.config import Settings, get_settings
from f01.providers.prompts import PLANNING_INSTRUCTIONS
from f01.api.dependencies import get_database, get_principal
from f01.domain.context_planning import UsageView
from f01.domain.projects import Principal
from f01.db.session import Database
from pydantic import BaseModel, ConfigDict, StringConstraints

from f01.api.dependencies import require_authenticated_identity
from f01.api.errors import ApplicationError, ErrorEnvelope
from f01.domain.planning import ProjectPlan
from f01.providers.base import PlanningProvider, ProviderError, ProviderErrorCode
from f01.providers.factory import get_planning_provider


class PlanRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    idea: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)
    ]


router = APIRouter(prefix="/v1", tags=["Planning"])

@router.get('/planning/usage',response_model=UsageView)
def planning_usage(database:Annotated[Database,Depends(get_database)],principal:Annotated[Principal,Depends(get_principal)],settings:Annotated[Settings,Depends(get_settings)]) -> UsageView:
    return service.usage(database,settings,principal.id)


@router.post(
    "/plan",
    response_model=ProjectPlan,
    dependencies=[Depends(require_authenticated_identity)],
    responses={
        status: {"model": ErrorEnvelope}
        for status in (401, 422, 429, 500, 502, 503, 504)
    },
    summary="Create a structured software product plan",
    description="Produces a proposal only. Does not save a project, build code or deploy software.",
)
async def plan_product(
    request: PlanRequest,
    http_request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[PlanningProvider, Depends(get_planning_provider)],
) -> ProjectPlan:
    attempt = None
    budget: DevelopmentBudget = http_request.app.state.development_planning_budget
    if settings.auth_mode == "oidc":
        principal = http_request.state.principal
        attempt, _ = await asyncio.to_thread(service.reserve, http_request.app.state.database, settings, principal.id, str(uuid4()), digest(request.idea), None, idea=request.idea)
    else:
        estimated = len(request.idea.encode())+len(PLANNING_INSTRUCTIONS.encode())+len(service.encode(ProjectPlan.model_json_schema()).encode())+512
        if estimated > settings.planning_input_tokens: raise ApplicationError("PLANNING_CONTEXT_TOO_LARGE")
        budget.reserve(settings, estimated+settings.planning_output_tokens)
    try:
        async with asyncio.timeout(settings.planning_timeout_seconds):
            result = ProjectPlan.model_validate(await provider.create_plan(request.idea))
        for secret in (settings.openai_api_key, settings.auth_gateway_token, settings.oidc_client_secret, settings.dev_api_token, settings.session_encryption_key):
            if secret and len(secret.get_secret_value()) >= 8 and secret.get_secret_value() in result.model_dump_json():
                raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
        if attempt:
            completed = await asyncio.to_thread(service.finish, http_request.app.state.database, settings, http_request.state.principal.id, attempt.id, None, None, http_request.state.auth_session.id)
            if completed.status != 'succeeded': raise ApplicationError(completed.error_code or 'PLANNING_ABANDONED')
        return result
    except ProviderError as exc:
        if attempt: await asyncio.to_thread(service.finish, http_request.app.state.database, settings, http_request.state.principal.id, attempt.id, None, exc.code.value)
        raise
    except ApplicationError:
        raise
    except (TimeoutError, asyncio.CancelledError):
        if attempt: await asyncio.to_thread(service.finish, http_request.app.state.database, settings, http_request.state.principal.id, attempt.id, None, 'PROVIDER_TIMEOUT')
        raise ProviderError(ProviderErrorCode.TIMEOUT) from None
    except Exception:
        if attempt: await asyncio.to_thread(service.finish, http_request.app.state.database, settings, http_request.state.principal.id, attempt.id, None, "INTERNAL_ERROR")
        raise ApplicationError("INTERNAL_ERROR") from None
    finally:
        if settings.auth_mode == "development": budget.release()
