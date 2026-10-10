import asyncio
import json
from collections.abc import Callable, Coroutine

import httpx
import pytest
from pydantic import SecretStr

from f01.domain.planning import ProjectPlan
from f01.domain.source import GenerationContext, SourceProposal
from f01.providers.base import ProviderError, ProviderErrorCode
from f01.providers.openai_source import MAX_RESPONSE_BYTES, OpenAISourceGenerationProvider
from tests.source_fixture import generation_context, initial_proposal


def response_body() -> dict[str, object]:
    return {"status": "completed", "output": [{"type": "message", "role": "assistant", "status": "completed",
        "content": [{"type": "output_text", "text": initial_proposal().model_dump_json()}]}]}


def call(context: GenerationContext, handler: Callable[[httpx.Request], httpx.Response] | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]], *,
         limit: int = 8000, deadline: float = 1, key: SecretStr | None = SecretStr("synthetic-generation-key")) -> None:
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAISourceGenerationProvider(client=client, api_key=key, model="configured-model", timeout_seconds=deadline)
            await provider.propose_source(context, limit)
    asyncio.run(run())


def test_source_adapter_strict_contract_usage_and_no_tools(project_plan: ProjectPlan) -> None:
    context = generation_context(project_plan)
    calls: list[dict[str, object]] = []
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        assert body["max_output_tokens"] == 8000 and body["store"] is False
        assert body["text"]["format"]["schema"] == SourceProposal.model_json_schema()
        assert body["text"]["format"]["strict"] is True
        assert body["input"] == context.model_dump_json()
        # Real browser acceptance found invisible utility styling, blocked form
        # events and unavailable opaque-origin storage. Every real generation
        # dispatch must receive the scaffold/browser constraints (not user data).
        policy = body["instructions"]
        assert "no Tailwind compiler" in policy and "actual plain CSS" in policy
        assert "never depend on onSubmit or confirm" in policy
        assert "never write" in policy and "before loading it" in policy
        assert "Preserve existing storage" in policy
        assert "INTERFACE QUALITY" in policy
        assert "flex-basis" in policy and "column flex parent" in policy
        assert "primary content in the initial viewport" in policy
        assert "gate writes on completed storage hydration" in policy
        assert "claim that browser tests ran" in policy
        assert "one identical template" in policy
        assert "tools" not in body and "OpenAI" not in str(SourceProposal.model_json_schema())
        return httpx.Response(200, json={**response_body(), "usage": {"input_tokens": 100, "output_tokens": 200}})
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAISourceGenerationProvider(client=client, api_key=SecretStr("synthetic-generation-key"), model="model", timeout_seconds=1)
            result = await provider.propose_source(context, 8000)
            assert result.proposal == initial_proposal() and result.input_tokens == 100 and result.output_tokens == 200
    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("status,body,code", [
    (401, {}, ProviderErrorCode.AUTHENTICATION), (429, {"error": {"code": "insufficient_quota"}}, ProviderErrorCode.QUOTA),
    (429, {}, ProviderErrorCode.RATE_LIMIT), (503, {}, ProviderErrorCode.UNAVAILABLE),
    (302, {}, ProviderErrorCode.ERROR), (200, {"status": "incomplete", "output": []}, ProviderErrorCode.INCOMPLETE_RESPONSE),
    (200, {"status": "completed", "output": []}, ProviderErrorCode.INVALID_RESPONSE),
    (200, {"status": "completed", "output": [{"type": "function_call", "arguments": "malicious"}]}, ProviderErrorCode.INVALID_RESPONSE),
    (200, {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "text": "private"}]}]}, ProviderErrorCode.REFUSED),
])
def test_errors_are_sanitized_no_retry_or_redirect(project_plan: ProjectPlan, status: int, body: dict[str, object], code: ProviderErrorCode) -> None:
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, headers={"Location": "https://untrusted.invalid/"}, json={**body, "private": "credential-body"})
    with pytest.raises(ProviderError) as error:
        call(generation_context(project_plan), handler)
    assert error.value.code == code and "credential-body" not in str(error.value)
    assert calls == 1


@pytest.mark.parametrize("usage", [{"output_tokens": 8001}, {"output_tokens": True}, {"input_tokens": -1}, {"input_tokens": 131073}, {"input_tokens": "12"}, "invalid"])
def test_reported_usage_is_bounded_and_typed(project_plan: ProjectPlan, usage: object) -> None:
    with pytest.raises(ProviderError, match="PROVIDER_INVALID_RESPONSE"):
        call(generation_context(project_plan), lambda _: httpx.Response(200, json={**response_body(), "usage": usage}))


def test_missing_usage_is_unknown_instead_of_estimated_execution_evidence(project_plan: ProjectPlan) -> None:
    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response_body()))) as client:
            provider = OpenAISourceGenerationProvider(client=client, api_key=SecretStr("synthetic-generation-key"), model="model", timeout_seconds=1)
            result = await provider.propose_source(generation_context(project_plan), 8000)
            assert result.input_tokens is None and result.output_tokens is None
    asyncio.run(run())


def test_oversized_response_malformed_json_secret_echo_and_wrong_base(project_plan: ProjectPlan) -> None:
    values: list[bytes] = [b"x" * (MAX_RESPONSE_BYTES + 1), b"invalid json"]
    for proposal in (
        initial_proposal().model_copy(update={"base_digest": "0" * 64}),
        initial_proposal().model_copy(update={"edits": (initial_proposal().edits[0].model_copy(update={"content": "synthetic-generation-key"}),)}),
    ):
        body = {"status": "completed", "output": [{"type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": proposal.model_dump_json()}]}]}
        values.append(json.dumps(body).encode())
        if "synthetic-generation-key" in proposal.model_dump_json():
            body["output"] = [{"type": "message", "role": "assistant", "status": "completed", "content": [
                {"type": "output_text", "text": proposal.model_dump_json().replace("synthetic-generation-key", "\\u0073ynthetic-generation-key")}]}]
            values.append(json.dumps(body).encode())
    for value in values:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=value)
        with pytest.raises(ProviderError, match="PROVIDER_INVALID_RESPONSE"):
            call(generation_context(project_plan), handler)


@pytest.mark.parametrize("limit", [0, -1, 16001])
def test_invalid_output_budget_never_contacts_provider(project_plan: ProjectPlan, limit: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Unexpected provider call")
    with pytest.raises(ProviderError, match="PROVIDER_INVALID_RESPONSE"):
        call(generation_context(project_plan), handler, limit=limit)


def test_missing_key_and_secret_containing_context_never_contacts_provider(project_plan: ProjectPlan) -> None:
    context = generation_context(project_plan)
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Unexpected provider call")
    with pytest.raises(ProviderError, match="PROVIDER_NOT_CONFIGURED"):
        call(context, handler, key=None)
    with pytest.raises(ProviderError, match="PROVIDER_INVALID_RESPONSE"):
        call(context.model_copy(update={"approved_brief": "synthetic-generation-key"}), handler)


def test_total_timeout_transport_failure_and_external_cancellation(project_plan: ProjectPlan) -> None:
    calls = 0
    async def slow(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(.03)
        return httpx.Response(200, json=response_body())
    with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT"):
        call(generation_context(project_plan), slow, deadline=.01)
    assert calls == 1
    def broken(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private diagnostic")
    with pytest.raises(ProviderError, match="PROVIDER_UNAVAILABLE") as error:
        call(generation_context(project_plan), broken)
    assert "private diagnostic" not in str(error.value)
    async def cancelled(_: httpx.Request) -> httpx.Response:
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        call(generation_context(project_plan), cancelled)
