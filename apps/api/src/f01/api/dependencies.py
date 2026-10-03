from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from f01.api.errors import ApplicationError
from f01.application.projects import resolve_principal
from f01.config import Settings, get_settings
from f01.db.session import Database
from f01.domain.projects import Principal
from f01.api.stream import credentials_valid
from f01.application.identity import OIDCVerifier, authenticate_session
import asyncio

authenticated_bearer = HTTPBearer(auto_error=False, scheme_name="AuthenticatedBearer", description="Verified provider API token plus server-owned session in OIDC mode; private local credential only in explicit development mode.")


async def require_authenticated_identity(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(authenticated_bearer)
    ],
) -> None:
    if credentials is None:
        raise ApplicationError("AUTHENTICATION_REQUIRED")
    if settings.auth_mode == "oidc":
        verifier: OIDCVerifier = request.app.state.oidc_verifier
        principal, session = await asyncio.to_thread(authenticate_session, request.app.state.database, settings, verifier,
            credentials.credentials, request.headers.get("x-f01-session", ""), request.headers.get("x-f01-csrf"), request.method not in ("GET", "HEAD", "OPTIONS"))
        request.state.principal, request.state.auth_session = principal, session
    elif not credentials_valid(settings, credentials.credentials):
        raise ApplicationError("AUTHENTICATION_REQUIRED")


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


def get_principal(
    request: Request,
    _authentication: None = Depends(require_authenticated_identity),
    settings: Settings = Depends(get_settings),
    database: Database = Depends(get_database),
) -> Principal:
    if settings.auth_mode == "oidc":
        principal: Principal = request.state.principal
        return principal
    return resolve_principal(database, settings.dev_auth_subject)
