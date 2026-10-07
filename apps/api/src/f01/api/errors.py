from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from f01.domain.errors import ApplicationError as ApplicationError
from f01.providers.base import ProviderError, ProviderErrorCode


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: UUID
    details: dict[str, object] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


APPLICATION_EXECUTION_ERRORS = {
    "EXECUTION_UNAVAILABLE": (503, "Real execution is unavailable until the trusted Docker runtime is configured and verified."),
    "PLAN_REVIEW_REQUIRED": (409, "Review the current plan before starting a real build."),
    "SOURCE_BASE_UNAVAILABLE": (409, "This version has no generated source. Create a new project for real execution."),
    "SOURCE_SECRET_REJECTED": (422, "Source or context contains a forbidden credential."),
    "REAL_BUILD_COMMAND_REQUIRED": (409, "Use real build controls for generated source versions."),
    "CLEANUP_PENDING": (409, "The previous sandbox is awaiting cleanup."),
    "VERIFICATION_REQUIRED": (409, "Required verification evidence is missing."),
}

PROVIDER_ERRORS: dict[ProviderErrorCode, tuple[int, str]] = {
    ProviderErrorCode.NOT_CONFIGURED: (
        503,
        "Planning is unavailable: the backend provider key is not configured.",
    ),
    ProviderErrorCode.AUTHENTICATION: (
        502,
        "The planning provider rejected the backend credentials or permissions.",
    ),
    ProviderErrorCode.QUOTA: (
        503,
        "The planning provider has exhausted its credits or usage allowance.",
    ),
    ProviderErrorCode.RATE_LIMIT: (
        429,
        "The planning provider is rate limited. Try again later.",
    ),
    ProviderErrorCode.TIMEOUT: (
        504,
        "The planning provider timed out. Try again later.",
    ),
    ProviderErrorCode.UNAVAILABLE: (
        503,
        "The planning provider is temporarily unavailable. Try again later.",
    ),
    ProviderErrorCode.INVALID_RESPONSE: (
        502,
        "The planning provider returned an invalid project plan.",
    ),
    ProviderErrorCode.INCOMPLETE_RESPONSE: (
        502,
        "The planning provider could not complete the project plan.",
    ),
    ProviderErrorCode.REFUSED: (
        422,
        "The planning provider declined this product idea.",
    ),
    ProviderErrorCode.ERROR: (
        502,
        "The planning provider could not process the request.",
    ),
}


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    request_id = uuid4()
    envelope = ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    headers = {"X-Request-ID": str(request_id)}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=status, content=envelope.model_dump(mode="json"), headers=headers
    )


async def _provider_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ProviderError)
    status, message = PROVIDER_ERRORS[exc.code]
    return _error_response(status, exc.code.value, message)


APPLICATION_ERRORS: dict[str, tuple[int, str]] = {
    **APPLICATION_EXECUTION_ERRORS,
    "RELEASE_NOT_RETRYABLE": (409, "Only a confirmed failed command with the same reviewed package can be retried."),
    "RELEASE_RECOVERY_REQUIRED": (409, "Resolve the saved provider observation before continuing."),
    "RELEASE_UNAVAILABLE": (503, "Production release support is unavailable until the exact packaging runtime is accepted."),
    "RELEASE_NOT_CONFIGURED": (503, "This project needs a separate production hosting target."),
    "RELEASE_IN_PROGRESS": (409, "A production release is in progress. Resolve it before changing this project."),
    "RELEASE_STALE_CONTEXT": (409, "Source, Brain, configuration or production changed. Review the current release context."),
    "RELEASE_VERIFICATION_REQUIRED": (409, "Only verified real source and production packages can be released."),
    "RELEASE_PACKAGE_INVALID": (409, "The saved production package failed integrity validation."),
    "RELEASE_URL_INVALID": (422, "The production URL is outside the allowed isolated hosting boundary."),
    "RELEASE_CONFIGURATION_LOCKED": (409, "The production target is already bound. Operator recovery is required to change it."),
    "AUTHENTICATION_REQUIRED": (401, "A valid authenticated session is required."),
    "IDENTITY_LINK_CONFLICT": (409, "Identity linking requires operator review; existing ownership was not changed."),
    "AUTH_RATE_LIMITED": (429, "Sign-in attempts are temporarily limited. Try again later."),
    "PLANNING_RATE_LIMITED": (429, "Your planning request allowance is temporarily exhausted."),
    "PLANNING_BUDGET_EXCEEDED": (429, "Your planning token budget is exhausted for this UTC day."),
    "PLANNING_IN_PROGRESS": (409, "A planning attempt is still pending. Inspect its saved status."),
    "PLANNING_STALE_CONTEXT": (409, "Project context changed. Your request is preserved; review current context before making a new plan."),
    "PLANNING_CANCELED": (409, "This planning attempt was canceled. No proposal was published."),
    "PLANNING_ABANDONED": (409, "This attempt could not be confirmed before its deadline. Start a reviewed new attempt."),
    "PLANNING_CONTEXT_TOO_LARGE": (422, "The bounded planning context exceeds this request's input allowance."),
    "NOT_FOUND": (404, "Project or resource not found."),
    "VALIDATION_ERROR": (422, "The request does not match the API contract."),
    "PRECONDITION_REQUIRED": (428, "Supply the current project ETag in If-Match."),
    "METADATA_CONFLICT": (
        412,
        "Project settings changed. Read the current project and retry.",
    ),
    "ACTIVE_RUN_EXISTS": (
        409,
        "An active run must finish or be canceled before archiving or recording a change.",
    ),
    "PROJECT_ARCHIVED": (409, "Unarchive this project before recording a change or starting a run."),
    "STALE_BRAIN_REVISION": (409, "The Brain context changed. Review the current project before resubmitting."),
    "STALE_BASE_VERSION": (409, "The current version changed. Review the current project before resubmitting."),
    "RUN_NOT_RETRYABLE": (409, "Only a failed simulation attempt can be retried."),
    "IDEMPOTENCY_KEY_REUSED": (
        409,
        "This idempotency key was used with different input.",
    ),
    "IDEMPOTENCY_IN_PROGRESS": (
        409,
        "This command is still processing. Retry with the same key.",
    ),
    "UNSUPPORTED_BRAIN_SCHEMA": (
        409,
        "This Brain schema version is not supported by this backend.",
    ),
    "DATABASE_UNAVAILABLE": (503, "Project storage is unavailable. Try again later."),
    "DATABASE_NOT_READY": (
        503,
        "Project storage migrations are not compatible with this backend.",
    ),
    "INTERNAL_ERROR": (500, "The request could not be completed."),
}


async def _application_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError)
    status, message = APPLICATION_ERRORS.get(
        exc.code, APPLICATION_ERRORS["INTERNAL_ERROR"]
    )
    return _error_response(
        status,
        exc.code if exc.code in APPLICATION_ERRORS else "INTERNAL_ERROR",
        message,
    )


async def _validation_error_handler(request: Request, _exc: Exception) -> JSONResponse:
    # FastAPI's default validation body includes caller input; never echo it here.
    return _error_response(
        422,
        "VALIDATION_ERROR",
        "Send an object with a non-empty idea of at most 10000 characters."
        if request.url.path == "/v1/plan"
        else "The request does not match the API contract.",
    )


async def _database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never serialize exception text, query parameters or connection configuration.
    if (
        isinstance(exc, DBAPIError)
        and getattr(exc.orig, "sqlstate", None) == "55P03"
        and request.method == "POST"
        and (request.url.path == "/v1/projects" or request.url.path.endswith(("/requests", "/runs", "/retry")))
    ):
        code = "IDEMPOTENCY_IN_PROGRESS"
    else:
        code = (
            "DATABASE_UNAVAILABLE"
            if isinstance(exc, DBAPIError)
            and getattr(exc.orig, "sqlstate", None) is None
            else "INTERNAL_ERROR"
        )
    status, message = APPLICATION_ERRORS[code]
    return _error_response(status, code, message)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProviderError, _provider_error_handler)
    app.add_exception_handler(ApplicationError, _application_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(SQLAlchemyError, _database_error_handler)
