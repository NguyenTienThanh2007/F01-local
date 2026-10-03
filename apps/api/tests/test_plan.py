import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine, Iterator
from contextlib import contextmanager
import json
import logging
from uuid import UUID

from fastapi.testclient import TestClient
import httpx
from pydantic import SecretStr
import pytest

from f01.api.errors import ErrorEnvelope
from f01.config import Settings
from f01.domain.planning import ProjectPlan
from f01.main import create_app
from f01.providers.base import PlanningProvider
from f01.providers.factory import get_planning_provider, get_provider_client

Handler = (
    Callable[[httpx.Request], httpx.Response]
    | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]
)
IDEA = "Build a CRM for a small real estate agency with leads and notes."


def authorization(settings: Settings) -> dict[str, str]:
    return {"Authorization": "Bearer " + settings.dev_api_token.get_secret_value()}


def completed_response(project_plan: ProjectPlan) -> dict[str, object]:
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": project_plan.model_dump_json()}
                ],
            }
        ],
    }


@contextmanager
def planning_client(settings: Settings, handler: Handler) -> Iterator[TestClient]:
    app = create_app(settings)

    async def mock_client() -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False
        ) as client:
            yield client

    app.dependency_overrides[get_provider_client] = mock_client
    with TestClient(app) as client:
        yield client


def assert_error(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status
    error = ErrorEnvelope.model_validate(response.json()).error
    assert error.code == code
    assert error.details == {}
    assert response.headers["X-Request-ID"] == str(error.request_id)
    UUID(str(error.request_id))


def test_plan_calls_openai_and_returns_validated_plan(
    settings: Settings, project_plan: ProjectPlan, caplog: pytest.LogCaptureFixture
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=completed_response(project_plan))

    caplog.set_level(logging.DEBUG)
    with planning_client(settings, respond) as client:
        response = client.post(
            "/v1/plan",
            json={"idea": "  " + IDEA + "  "},
            headers=authorization(settings),
        )

    assert response.status_code == 200
    assert ProjectPlan.model_validate(response.json()) == project_plan
    assert len(requests) == 1
    upstream = requests[0]
    assert str(upstream.url) == "https://api.openai.com/v1/responses"
    assert upstream.method == "POST"
    assert settings.openai_api_key is not None
    assert (
        upstream.headers["Authorization"]
        == "Bearer " + settings.openai_api_key.get_secret_value()
    )
    body = json.loads(upstream.content)
    assert body["input"] == IDEA
    assert body["model"] == settings.openai_model
    assert body["store"] is False
    assert body["max_output_tokens"] == 3000
    assert "tools" not in body
    output_format = body["text"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["strict"] is True
    schema = output_format["schema"]
    for model_schema in [schema, *schema["$defs"].values()]:
        assert model_schema["additionalProperties"] is False
        assert set(model_schema["required"]) == set(model_schema["properties"])
    assert settings.openai_api_key.get_secret_value() not in response.text + caplog.text
    assert settings.dev_api_token.get_secret_value() not in response.text + caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {},
        None,
        [],
        "a product idea",
        {"idea": 42},
        {"idea": True},
        {"idea": None},
        {"idea": ""},
        {"idea": " \n\t "},
        {"idea": "x" * 10001},
        {"idea": IDEA, "OPENAI_API_KEY": "do-not-echo-caller-input"},
    ],
)
def test_invalid_input_is_rejected_before_provider_call(
    settings: Settings, payload: object
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    with planning_client(settings, respond) as client:
        response = client.post(
            "/v1/plan", json=payload, headers=authorization(settings)
        )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert not requests
    assert "do-not-echo-caller-input" not in response.text


def test_invalid_json_is_not_echoed(settings: Settings) -> None:
    with planning_client(settings, lambda _: httpx.Response(500)) as client:
        response = client.post(
            "/v1/plan",
            content='{"idea": "do-not-echo-caller-input",',
            headers={**authorization(settings), "Content-Type": "application/json"},
        )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert "do-not-echo-caller-input" not in response.text


@pytest.mark.parametrize(
    "header", [None, "Bearer wrong-token", "Basic wrong-token", "Bearer"]
)
def test_development_token_is_required_before_provider_call(
    settings: Settings, header: str | None
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    with planning_client(settings, respond) as client:
        response = client.post(
            "/v1/plan",
            json={"idea": IDEA},
            headers={} if header is None else {"Authorization": header},
        )
    assert_error(response, 401, "AUTHENTICATION_REQUIRED")
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert not requests


@pytest.mark.parametrize("key", [None, SecretStr(""), SecretStr("   ")])
def test_missing_key_is_a_safe_error_without_outbound_call(
    settings: Settings, key: SecretStr | None
) -> None:
    configured = settings.model_copy(update={"openai_api_key": key})
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    with planning_client(configured, respond) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(configured)
        )
        assert client.get("/v1/health/live").json() == {"status": "alive"}
    assert_error(response, 503, "PROVIDER_NOT_CONFIGURED")
    assert not requests


@pytest.mark.parametrize(
    "upstream_status,upstream_code,upstream_type,status,code",
    [
        (
            401,
            "invalid_api_key",
            "invalid_request_error",
            502,
            "PROVIDER_AUTHENTICATION_FAILED",
        ),
        (403, None, None, 502, "PROVIDER_AUTHENTICATION_FAILED"),
        (
            429,
            "insufficient_quota",
            "insufficient_quota",
            503,
            "PROVIDER_QUOTA_EXCEEDED",
        ),
        (429, "credit_balance_exhausted", None, 503, "PROVIDER_QUOTA_EXCEEDED"),
        (429, "project_spend_limit_exceeded", None, 503, "PROVIDER_QUOTA_EXCEEDED"),
        (
            429,
            "organization_spend_limit_exceeded",
            None,
            503,
            "PROVIDER_QUOTA_EXCEEDED",
        ),
        (
            429,
            "organization_usage_limit_exceeded",
            None,
            503,
            "PROVIDER_QUOTA_EXCEEDED",
        ),
        (429, "billing_hard_limit_reached", None, 503, "PROVIDER_QUOTA_EXCEEDED"),
        (429, "new-billing-code", "insufficient_quota", 503, "PROVIDER_QUOTA_EXCEEDED"),
        (429, "slow_down", "rate_limit_error", 429, "PROVIDER_RATE_LIMITED"),
        (400, "invalid_request_error", None, 502, "PROVIDER_ERROR"),
        (404, "model_not_found", None, 502, "PROVIDER_ERROR"),
        (500, None, None, 503, "PROVIDER_UNAVAILABLE"),
        (503, None, None, 503, "PROVIDER_UNAVAILABLE"),
        (408, None, None, 504, "PROVIDER_TIMEOUT"),
        (504, None, None, 504, "PROVIDER_TIMEOUT"),
        (302, None, None, 502, "PROVIDER_ERROR"),
    ],
)
def test_upstream_errors_are_sanitized_without_retries(
    settings: Settings,
    upstream_status: int,
    upstream_code: str | None,
    upstream_type: str | None,
    status: int,
    code: str,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    requests: list[httpx.Request] = []
    assert settings.openai_api_key is not None
    credential = settings.openai_api_key.get_secret_value()

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            upstream_status,
            headers={"Location": "https://example.invalid/redirect"},
            json={
                "error": {
                    "code": upstream_code,
                    "type": upstream_type,
                    "message": "Rejected credential: " + credential,
                }
            },
        )

    caplog.set_level(logging.DEBUG)
    with planning_client(settings, respond) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, status, code)
    assert len(requests) == 1
    captured = capsys.readouterr()
    assert credential not in response.text + caplog.text + captured.out + captured.err
    assert "Rejected credential" not in response.text + caplog.text


def test_malformed_error_body_is_safe(settings: Settings) -> None:
    with planning_client(
        settings, lambda _: httpx.Response(429, content=b"not-json")
    ) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, 429, "PROVIDER_RATE_LIMITED")


@pytest.mark.parametrize(
    "failure,status,code",
    [
        (httpx.ReadTimeout, 504, "PROVIDER_TIMEOUT"),
        (httpx.ConnectError, 503, "PROVIDER_UNAVAILABLE"),
        (RuntimeError, 502, "PROVIDER_ERROR"),
    ],
)
def test_transport_exceptions_cannot_leak_credentials(
    settings: Settings,
    failure: type[Exception],
    status: int,
    code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert settings.openai_api_key is not None
    credential = settings.openai_api_key.get_secret_value()

    def fail(_request: httpx.Request) -> httpx.Response:
        raise failure("Credential: " + credential)

    caplog.set_level(logging.DEBUG)
    with planning_client(settings, fail) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, status, code)
    assert credential not in response.text + caplog.text


def test_entire_provider_call_has_a_deadline(settings: Settings) -> None:
    async def slow(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200)

    configured = settings.model_copy(update={"planning_timeout_seconds": 0.01})
    with planning_client(configured, slow) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(configured)
        )
    assert_error(response, 504, "PROVIDER_TIMEOUT")


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"status": "queued", "output": []},
        {"status": "completed", "output": []},
        {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "not-json"}],
                }
            ],
        },
        {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "{}"}],
                }
            ],
        },
    ],
)
def test_malformed_provider_output_is_not_a_success(
    settings: Settings, body: object
) -> None:
    with planning_client(settings, lambda _: httpx.Response(200, json=body)) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, 502, "PROVIDER_INVALID_RESPONSE")


@pytest.mark.parametrize(
    "invalid_field", ["target_users", "core_features", "implementation_milestones"]
)
def test_empty_plan_sections_are_rejected(
    settings: Settings, project_plan: ProjectPlan, invalid_field: str
) -> None:
    data = project_plan.model_dump()
    data[invalid_field] = []
    body = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps(data)}],
            }
        ],
    }
    with planning_client(settings, lambda _: httpx.Response(200, json=body)) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, 502, "PROVIDER_INVALID_RESPONSE")


def test_incomplete_output_is_rejected_even_when_json_is_valid(
    settings: Settings, project_plan: ProjectPlan
) -> None:
    body = completed_response(project_plan)
    body["status"] = "incomplete"
    with planning_client(settings, lambda _: httpx.Response(200, json=body)) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, 502, "PROVIDER_INCOMPLETE_RESPONSE")


def test_refusal_text_is_not_returned(settings: Settings) -> None:
    body = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "refusal", "refusal": "do-not-echo-provider-text"}
                ],
            }
        ],
    }
    with planning_client(settings, lambda _: httpx.Response(200, json=body)) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, 422, "PROVIDER_REFUSED")
    assert "do-not-echo-provider-text" not in response.text


def test_reasoning_items_do_not_hide_the_plan(
    settings: Settings, project_plan: ProjectPlan
) -> None:
    body = completed_response(project_plan)
    outputs = body["output"]
    assert isinstance(outputs, list)
    outputs.insert(0, {"type": "reasoning", "summary": []})
    with planning_client(settings, lambda _: httpx.Response(200, json=body)) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert response.status_code == 200
    assert ProjectPlan.model_validate(response.json()) == project_plan


def test_provider_cannot_echo_the_configured_key_in_a_valid_plan(
    settings: Settings,
    project_plan: ProjectPlan,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert settings.openai_api_key is not None
    credential = settings.openai_api_key.get_secret_value()
    echoed = project_plan.model_copy(
        update={"product_summary": "Credential: " + credential}
    )
    with planning_client(
        settings, lambda _: httpx.Response(200, json=completed_response(echoed))
    ) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, 502, "PROVIDER_INVALID_RESPONSE")
    assert credential not in response.text + caplog.text


def test_route_accepts_another_provider_without_openai_types(
    settings: Settings, project_plan: ProjectPlan
) -> None:
    class AlternativeProvider:
        async def create_plan(self, idea: str) -> ProjectPlan:
            assert idea == IDEA
            return project_plan

    def alternative() -> PlanningProvider:
        return AlternativeProvider()

    app = create_app(settings)
    app.dependency_overrides[get_planning_provider] = alternative
    with TestClient(app) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert response.status_code == 200
    assert ProjectPlan.model_validate(response.json()) == project_plan


def test_unexpected_adapter_failure_is_sanitized(settings: Settings) -> None:
    class BrokenProvider:
        async def create_plan(self, idea: str) -> ProjectPlan:
            assert settings.openai_api_key is not None
            raise RuntimeError(settings.openai_api_key.get_secret_value())

    app = create_app(settings)
    app.dependency_overrides[get_planning_provider] = BrokenProvider
    with TestClient(app) as client:
        response = client.post(
            "/v1/plan", json={"idea": IDEA}, headers=authorization(settings)
        )
    assert_error(response, 500, "INTERNAL_ERROR")
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() not in response.text


def test_openapi_documents_the_input_output_and_development_auth(
    settings: Settings,
) -> None:
    schema = create_app(settings).openapi()
    operation = schema["paths"]["/v1/plan"]["post"]
    assert operation["security"] == [{"AuthenticatedBearer": []}]
    assert (
        "PlanRequest"
        in operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    )
    assert (
        "ProjectPlan"
        in operation["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ]
    )
    assert (
        schema["components"]["schemas"]["PlanRequest"]["additionalProperties"] is False
    )
    assert schema["components"]["schemas"]["ProjectPlan"]["required"] == [
        "project_title",
        "product_summary",
        "target_users",
        "core_features",
        "recommended_stack",
        "implementation_milestones",
    ]
