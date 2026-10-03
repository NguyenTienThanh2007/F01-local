"""Private BFF endpoints. Credentials and provider tokens never go to browser JSON."""
from hmac import compare_digest
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
from f01.api.dependencies import authenticated_bearer, get_database
from f01.application.identity import OIDCVerifier, start_login, finish_login, session_record, unseal, digest, revoke_session
from f01.config import Settings, get_settings
from f01.db.session import Database
from f01.domain.errors import ApplicationError

router = APIRouter(prefix="/v1/auth", tags=["Identity"])

def gateway(settings: Annotated[Settings, Depends(get_settings)], credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(authenticated_bearer)]) -> None:
    if settings.auth_mode != "oidc" or credentials is None or not compare_digest(credentials.credentials.encode(), settings.auth_gateway_token.get_secret_value().encode()):
        raise ApplicationError("AUTHENTICATION_REQUIRED")

class Callback(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    state: str = Field(min_length=40, max_length=100)
    binding: str = Field(min_length=40, max_length=100)
    code: str = Field(min_length=1, max_length=2048)

class SessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    session: str = Field(min_length=40, max_length=100)
    csrf: str = Field(min_length=40, max_length=100)

DB = Annotated[Database, Depends(get_database)]
Config = Annotated[Settings, Depends(get_settings)]

@router.post("/start", dependencies=[Depends(gateway)])
def start(database: DB, settings: Config) -> dict[str, str]:
    return start_login(database, settings)

@router.post("/callback", dependencies=[Depends(gateway)])
async def callback(body: Callback, request: Request, database: DB, settings: Config) -> dict[str, str]:
    verifier: OIDCVerifier = request.app.state.oidc_verifier
    return await finish_login(database, settings, verifier, body.state, body.binding, body.code)

@router.post("/access", dependencies=[Depends(gateway)])
def access(body: SessionInput, request: Request, database: DB, settings: Config) -> dict[str, str]:
    row = session_record(database, settings, body.session)
    if not compare_digest(row.csrf_hash, digest(body.csrf)):
        raise ApplicationError("AUTHENTICATION_REQUIRED")
    token = unseal(settings, row.access_encrypted)
    verifier: OIDCVerifier = request.app.state.oidc_verifier
    verifier.access(token)
    return {"access_token": token}

@router.post("/logout", dependencies=[Depends(gateway)])
def logout(body: SessionInput, database: DB, settings: Config) -> dict[str, bool]:
    revoke_session(database, settings, body.session, body.csrf)
    return {"signed_out": True}
