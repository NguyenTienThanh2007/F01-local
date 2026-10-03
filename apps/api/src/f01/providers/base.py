from enum import StrEnum
from typing import Protocol

from f01.domain.planning import ProjectPlan


class ProviderErrorCode(StrEnum):
    NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    AUTHENTICATION = "PROVIDER_AUTHENTICATION_FAILED"
    QUOTA = "PROVIDER_QUOTA_EXCEEDED"
    RATE_LIMIT = "PROVIDER_RATE_LIMITED"
    TIMEOUT = "PROVIDER_TIMEOUT"
    UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"
    INCOMPLETE_RESPONSE = "PROVIDER_INCOMPLETE_RESPONSE"
    REFUSED = "PROVIDER_REFUSED"
    ERROR = "PROVIDER_ERROR"


class ProviderError(Exception):
    """Contains only an application-owned code, never a provider error body."""

    def __init__(self, code: ProviderErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class PlanningProvider(Protocol):
    async def create_plan(self, idea: str) -> ProjectPlan: ...


class ContextPlanningProvider(Protocol):
    async def create_context_plan(self, context_json: str, maximum_output_tokens: int) -> "PlanningResult": ...


from f01.domain.context_planning import PlanningResult
