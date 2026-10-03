import asyncio
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Request, BackgroundTasks
from f01.api.dependencies import get_database, get_principal
from f01.application import planning as service
from f01.application.identity import digest
from f01.config import Settings, get_settings
from f01.db.session import Database
from f01.domain.context_planning import PlanInput, AttemptRecord, ProposalList, ProposalRecord
from f01.domain.projects import Principal
from f01.providers.base import ContextPlanningProvider, ProviderError, ProviderErrorCode
from f01.providers.factory import get_context_provider
from f01.api.errors import ErrorEnvelope
from f01.domain.context_planning import PlanningResult

router = APIRouter(prefix="/v1/projects/{project_id}/planning", tags=["Contextual planning"], responses={code:{"model":ErrorEnvelope} for code in (401,404,409,422,429,500,503)})
DB = Annotated[Database, Depends(get_database)]
Owner = Annotated[Principal, Depends(get_principal)]
Config = Annotated[Settings, Depends(get_settings)]

@router.post("/attempts", response_model=AttemptRecord, status_code=202)
async def plan(project_id: UUID, body: PlanInput, request: Request, background: BackgroundTasks, database: DB, principal: Owner, settings: Config,
    provider: Annotated[ContextPlanningProvider, Depends(get_context_provider)],
    idempotency_key: Annotated[str, Header(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")]) -> AttemptRecord:
    attempt, prompt = await asyncio.to_thread(service.reserve, database, settings, principal.id, idempotency_key,
        digest(str(project_id)+body.model_dump_json()), project_id, body)
    if prompt is None: return attempt
    auth = getattr(request.state, "auth_session", None)
    async def generate() -> None:
        result = None
        error = None
        try:
            async with asyncio.timeout(settings.planning_timeout_seconds):
                result = PlanningResult.model_validate(await provider.create_context_plan(prompt, settings.planning_output_tokens))
                if result.output_tokens is not None and result.output_tokens > settings.planning_output_tokens or result.input_tokens is not None and result.input_tokens > settings.planning_input_tokens:
                    raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
                for secret in (settings.openai_api_key,settings.auth_gateway_token,settings.oidc_client_secret,settings.dev_api_token,settings.session_encryption_key):
                    if secret and len(secret.get_secret_value()) >= 8 and secret.get_secret_value() in result.model_dump_json():
                        raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
        except ProviderError as exc: error = exc.code.value
        except (TimeoutError, asyncio.CancelledError): error = ProviderErrorCode.TIMEOUT.value
        except Exception: error = ProviderErrorCode.INVALID_RESPONSE.value
        await asyncio.to_thread(service.finish, database, settings, principal.id, attempt.id, result, error, auth.id if auth else None)
    background.add_task(generate)
    return attempt

@router.get("/attempts/{attempt_id}", response_model=AttemptRecord)
def attempt(project_id: UUID, attempt_id: UUID, database: DB, principal: Owner) -> AttemptRecord:
    return service.read_attempt(database, principal.id, project_id, attempt_id)

@router.post("/attempts/{attempt_id}/cancel", response_model=AttemptRecord)
def cancel(project_id: UUID, attempt_id: UUID, database: DB, principal: Owner) -> AttemptRecord:
    return service.read_attempt(database, principal.id, project_id, attempt_id, True)

@router.get("/proposals", response_model=ProposalList)
def list_proposals(project_id: UUID, database: DB, principal: Owner) -> ProposalList:
    return ProposalList(items=service.proposals(database, principal.id, project_id))

@router.post("/proposals/{proposal_id}/review", response_model=ProposalRecord)
def review(project_id: UUID, proposal_id: UUID, database: DB, principal: Owner) -> ProposalRecord:
    return service.review(database, principal.id, project_id, proposal_id)
