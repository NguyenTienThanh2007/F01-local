import asyncio

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from f01.domain.planning import ProjectPlan
from f01.domain.context_planning import ContextPlan, PlanningResult
from f01.providers.base import ProviderError, ProviderErrorCode

RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_OUTPUT_TOKENS = 3000
from f01.providers.prompts import CONTEXT_INSTRUCTIONS, PLANNING_INSTRUCTIONS
QUOTA_CODES = {
    "insufficient_quota",
    "billing_hard_limit_reached",
    "credit_balance_exhausted",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
}


class _WireModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore", hide_input_in_errors=True)


class _Content(_WireModel):
    type: str
    text: str | None = None


class _Output(_WireModel):
    type: str
    role: str | None = None
    status: str | None = None
    content: list[_Content] = Field(default_factory=list)


class _Response(_WireModel):
    status: str
    output: list[_Output] = Field(default_factory=list)


class _Error(_WireModel):
    code: str | None = None
    type: str | None = None


class _ErrorResponse(_WireModel):
    error: _Error


def _http_error(response: httpx.Response) -> ProviderError:
    status = response.status_code
    if status in {401, 403}:
        return ProviderError(ProviderErrorCode.AUTHENTICATION)
    if status == 429:
        try:
            error = _ErrorResponse.model_validate_json(response.content).error
            if error.type == "insufficient_quota" or error.code in QUOTA_CODES:
                return ProviderError(ProviderErrorCode.QUOTA)
        except ValidationError:
            pass
        return ProviderError(ProviderErrorCode.RATE_LIMIT)
    if status in {408, 504}:
        return ProviderError(ProviderErrorCode.TIMEOUT)
    if status >= 500:
        return ProviderError(ProviderErrorCode.UNAVAILABLE)
    return ProviderError(ProviderErrorCode.ERROR)


def _parse_plan(response: httpx.Response) -> ProjectPlan:
    try:
        result = _Response.model_validate_json(response.content)
        messages = [item for item in result.output if item.type == "message"]
        if any(
            part.type == "refusal" for message in messages for part in message.content
        ):
            raise ProviderError(ProviderErrorCode.REFUSED)
        if result.status == "incomplete":
            raise ProviderError(ProviderErrorCode.INCOMPLETE_RESPONSE)
        if result.status != "completed":
            raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
        texts = [
            part.text
            for message in messages
            if message.role == "assistant" and message.status == "completed"
            for part in message.content
            if part.type == "output_text" and part.text is not None
        ]
        if not texts:
            raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
        return ProjectPlan.model_validate_json("".join(texts))
    except ValidationError:
        raise ProviderError(ProviderErrorCode.INVALID_RESPONSE) from None


class OpenAIPlanningProvider:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        api_key: SecretStr | None,
        model: str,
        timeout_seconds: float,
        maximum_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._maximum_output_tokens = maximum_output_tokens

    async def create_plan(self, idea: str) -> ProjectPlan:
        if self._api_key is None or not self._api_key.get_secret_value().strip():
            raise ProviderError(ProviderErrorCode.NOT_CONFIGURED)
        try:
            # One bounded call; no redirects, tools, retries or persisted response object.
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._client.post(
                    RESPONSES_URL,
                    headers={
                        "Authorization": "Bearer " + self._api_key.get_secret_value()
                    },
                    json={
                        "model": self._model,
                        "instructions": PLANNING_INSTRUCTIONS,
                        "input": idea,
                        "store": False,
                        "max_output_tokens": self._maximum_output_tokens,
                        "text": {
                            "format": {
                                "type": "json_schema",
                                "name": "project_plan",
                                "strict": True,
                                "schema": ProjectPlan.model_json_schema(),
                            }
                        },
                    },
                    follow_redirects=False,
                )
            if response.status_code != 200:
                raise _http_error(response)
            plan = _parse_plan(response)
            if self._api_key.get_secret_value() in plan.model_dump_json():
                raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
            return plan
        except ProviderError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderError(ProviderErrorCode.TIMEOUT) from None
        except httpx.RequestError:
            raise ProviderError(ProviderErrorCode.UNAVAILABLE) from None
        except Exception:
            # Transport/validation exceptions may contain credentials or echoed input.
            raise ProviderError(ProviderErrorCode.ERROR) from None

    async def create_context_plan(self, context_json: str, maximum_output_tokens: int) -> PlanningResult:
        if self._api_key is None or not self._api_key.get_secret_value().strip():
            raise ProviderError(ProviderErrorCode.NOT_CONFIGURED)
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client.stream("POST", RESPONSES_URL, headers={"Authorization": "Bearer " + self._api_key.get_secret_value()},
                    json={"model": self._model, "instructions": CONTEXT_INSTRUCTIONS, "input": context_json, "store": False,
                        "max_output_tokens": maximum_output_tokens, "text": {"format": {"type": "json_schema", "name": "context_plan", "strict": True, "schema": ContextPlan.model_json_schema()}}},
                    follow_redirects=False) as response:
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 262144: raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
                    buffered = httpx.Response(response.status_code, content=bytes(raw))
            if buffered.status_code != 200: raise _http_error(buffered)
            result = _Response.model_validate_json(buffered.content)
            messages = [item for item in result.output if item.type == "message"]
            if any(part.type == "refusal" for item in messages for part in item.content): raise ProviderError(ProviderErrorCode.REFUSED)
            if result.status == "incomplete": raise ProviderError(ProviderErrorCode.INCOMPLETE_RESPONSE)
            if result.status != "completed": raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
            texts = [part.text for item in messages if item.role == "assistant" and item.status == "completed" for part in item.content if part.type == "output_text" and part.text is not None]
            if not texts: raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
            content = ContextPlan.model_validate_json("".join(texts))
            if self._api_key.get_secret_value() in content.model_dump_json(): raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
            usage = buffered.json().get("usage") or {}
            inp, out = usage.get("input_tokens"), usage.get("output_tokens")
            if inp is not None and (type(inp) is not int or not 0 <= inp <= 1000000) or out is not None and (type(out) is not int or not 0 <= out <= maximum_output_tokens):
                raise ProviderError(ProviderErrorCode.INVALID_RESPONSE)
            return PlanningResult(content=content, input_tokens=inp, output_tokens=out)
        except ProviderError: raise
        except (TimeoutError, httpx.TimeoutException): raise ProviderError(ProviderErrorCode.TIMEOUT) from None
        except httpx.RequestError: raise ProviderError(ProviderErrorCode.UNAVAILABLE) from None
        except Exception: raise ProviderError(ProviderErrorCode.INVALID_RESPONSE) from None
