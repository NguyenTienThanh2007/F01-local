from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends

from f01.config import Settings, get_settings
from f01.providers.base import PlanningProvider, ContextPlanningProvider
from f01.providers.openai import OpenAIPlanningProvider


async def get_provider_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.planning_timeout_seconds, connect=10.0),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        yield client


def get_planning_provider(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[httpx.AsyncClient, Depends(get_provider_client)],
) -> PlanningProvider:
    # Future adapters implement PlanningProvider; the route and domain stay unchanged.
    return OpenAIPlanningProvider(
        client=client,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout_seconds=settings.planning_timeout_seconds,
        maximum_output_tokens=settings.planning_output_tokens,
    )


def get_context_provider(settings: Annotated[Settings, Depends(get_settings)], client: Annotated[httpx.AsyncClient, Depends(get_provider_client)]) -> ContextPlanningProvider:
    return OpenAIPlanningProvider(client=client, api_key=settings.openai_api_key, model=settings.openai_model,
        timeout_seconds=settings.planning_timeout_seconds, maximum_output_tokens=settings.planning_output_tokens)
