"""Verified OIDC identities and revocable, opaque server-side sessions."""
import base64
import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from threading import Lock
from urllib.parse import urlencode
from uuid import UUID, uuid4
from typing import Any

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from sqlalchemy import select, text, func, update
from sqlalchemy.dialects.postgresql import insert

from f01.config import Settings
from f01.db.models import AuthFlow, AuthSession, ExternalIdentity, User
from f01.db.session import Database
from f01.domain.errors import ApplicationError
from f01.domain.projects import Principal


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def seal(settings: Settings, value: str) -> str:
    return Fernet(settings.session_encryption_key.get_secret_value().encode()).encrypt(value.encode()).decode()


def unseal(settings: Settings, value: str) -> str:
    try:
        return Fernet(settings.session_encryption_key.get_secret_value().encode()).decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        raise ApplicationError("AUTHENTICATION_REQUIRED") from None


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    expires_at: datetime
    display_name: str
    email: str | None


class OIDCVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._keys: dict[str, jwt.PyJWK] = {}
        self._loaded = 0.0
        self._last_fetch = -100.0
        self._lock = Lock()

    def _key(self, kid: str) -> jwt.PyJWK:
        with self._lock:
            now = time.monotonic()
            if now - self._loaded > 300 or kid not in self._keys:
                if now - self._last_fetch < 5:
                    raise ApplicationError("AUTHENTICATION_REQUIRED")
                self._last_fetch = now
                try:
                    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
                        with client.stream("GET", self.settings.oidc_jwks_url) as response:
                            if response.status_code != 200:
                                raise ValueError()
                            body = bytearray()
                            for chunk in response.iter_bytes():
                                body.extend(chunk)
                                if len(body) > 262144:
                                    raise ValueError()
                    import json
                    data = json.loads(body)
                    if not isinstance(data, dict) or not isinstance(data.get("keys"), list) or len(data["keys"]) > 100:
                        raise ValueError()
                    keys: dict[str, jwt.PyJWK] = {}
                    for item in data["keys"]:
                        if item.get("kty") != "RSA" or item.get("use", "sig") != "sig" or item.get("alg", "RS256") != "RS256":
                            continue
                        key = jwt.PyJWK.from_dict(item, algorithm="RS256")
                        if isinstance(key.key, RSAPublicKey) and key.key.key_size >= 2048 and key.key_id:
                            keys[key.key_id] = key
                    self._keys, self._loaded = keys, now
                except Exception:
                    raise ApplicationError("AUTHENTICATION_REQUIRED") from None
            if kid not in self._keys:
                raise ApplicationError("AUTHENTICATION_REQUIRED")
            return self._keys[kid]

    def claims(self, token: str, audience: str) -> dict[str, Any]:
        try:
            if len(token) > 16384:
                raise ValueError()
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise ValueError()
            result: dict[str, Any] = jwt.decode(token, self._key(header["kid"]), algorithms=["RS256"],
                audience=audience, issuer=self.settings.oidc_issuer,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]})
            if not isinstance(result["sub"], str) or not 1 <= len(result["sub"]) <= 200:
                raise ValueError()
            return result
        except Exception:
            raise ApplicationError("AUTHENTICATION_REQUIRED") from None

    def access(self, token: str) -> VerifiedIdentity:
        claims = self.claims(token, self.settings.oidc_api_audience)
        return VerifiedIdentity(self.settings.oidc_issuer, claims["sub"], datetime.fromtimestamp(claims["exp"], UTC), "Signed-in owner", None)

    def login(self, access: str, identity: str, nonce_hash: str) -> VerifiedIdentity:
        verified = self.access(access)
        claims = self.claims(identity, self.settings.oidc_client_id)
        if claims["sub"] != verified.subject or not isinstance(claims.get("nonce"), str) or not compare_digest(digest(claims["nonce"]), nonce_hash):
            raise ApplicationError("AUTHENTICATION_REQUIRED")
        audiences = claims["aud"] if isinstance(claims["aud"], list) else [claims["aud"]]
        if (len(audiences) > 1 or "azp" in claims) and claims.get("azp") != self.settings.oidc_client_id:
            raise ApplicationError("AUTHENTICATION_REQUIRED")
        if "at_hash" in claims:
            expected = base64.urlsafe_b64encode(hashlib.sha256(access.encode()).digest()[:16]).rstrip(b"=").decode()
            if not isinstance(claims["at_hash"], str) or not compare_digest(expected, claims["at_hash"]):
                raise ApplicationError("AUTHENTICATION_REQUIRED")
        name = claims.get("name", "Signed-in owner")
        email = claims.get("email") if claims.get("email_verified") is True else None
        return VerifiedIdentity(verified.issuer, verified.subject,
            min(verified.expires_at, datetime.fromtimestamp(claims["exp"], UTC)),
            name[:100] if isinstance(name, str) and name else "Signed-in owner",
            email if isinstance(email, str) and len(email) <= 320 else None)


def resolve_identity(database: Database, identity: VerifiedIdentity, *, existing_user_id: UUID | None = None) -> Principal:
    with database.session() as session, session.begin():
        # Serialize a subject's first login/link without trusting email or browser user IDs.
        lock = int(digest(identity.issuer + "\0" + identity.subject)[:15], 16)
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        external = session.scalar(select(ExternalIdentity).where(ExternalIdentity.issuer == identity.issuer, ExternalIdentity.subject == identity.subject))
        if external:
            if existing_user_id is not None and external.user_id != existing_user_id:
                raise ApplicationError("IDENTITY_LINK_CONFLICT")
            user = session.get(User, external.user_id)
        elif existing_user_id is not None:
            user = session.get(User, existing_user_id, with_for_update=True)
            if user is None or user.identity_issuer != "f01-development":
                raise ApplicationError("IDENTITY_LINK_CONFLICT")
            if session.scalar(select(ExternalIdentity.id).where(ExternalIdentity.user_id == user.id)):
                raise ApplicationError("IDENTITY_LINK_CONFLICT")
        else:
            uid = uuid4()
            user = User(id=uid, identity_issuer="oidc", identity_subject=str(uid), display_name=identity.display_name, email=identity.email, created_at=datetime.now(UTC))
            session.add(user); session.flush()
        assert user is not None
        if external is None:
            session.add(ExternalIdentity(id=uuid4(), user_id=user.id, issuer=identity.issuer, subject=identity.subject, created_at=datetime.now(UTC)))
        return Principal(id=user.id, display_name=user.display_name, identity_mode="oidc")


def start_login(database: Database, settings: Settings) -> dict[str, str]:
    now = datetime.now(UTC)
    state, binding, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
    with database.session() as session, session.begin():
        session.execute(text("SELECT pg_advisory_xact_lock(204201)"))
        count = session.scalar(select(func.count()).select_from(AuthFlow).where(AuthFlow.created_at > now - timedelta(minutes=1))) or 0
        if count >= 60:
            raise ApplicationError("AUTH_RATE_LIMITED")
        session.add(AuthFlow(id=uuid4(), state_hash=digest(state), binding_hash=digest(binding), nonce_hash=digest(nonce),
            verifier_encrypted=seal(settings, verifier), created_at=now, expires_at=now+timedelta(minutes=5)))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = settings.oidc_authorization_url + "?" + urlencode({"response_type": "code", "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri, "scope": "openid profile email", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256", "audience": settings.oidc_api_audience})
    return {"authorization_url": url, "binding": binding}


async def finish_login(database: Database, settings: Settings, verifier: OIDCVerifier, state: str, binding: str, code: str) -> dict[str, str]:
    now = datetime.now(UTC)
    with database.session() as session, session.begin():
        flow = session.scalar(select(AuthFlow).where(AuthFlow.state_hash == digest(state)).with_for_update())
        if flow is None or flow.consumed_at or flow.expires_at <= now or not compare_digest(flow.binding_hash, digest(binding)):
            raise ApplicationError("AUTHENTICATION_REQUIRED")
        flow.consumed_at = now
        nonce_hash, pkce = flow.nonce_hash, unseal(settings, flow.verifier_encrypted)
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False) as client:
            async with client.stream("POST", settings.oidc_token_url, data={"grant_type": "authorization_code", "code": code,
                "redirect_uri": settings.oidc_redirect_uri, "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret.get_secret_value(), "code_verifier": pkce}) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 65536: raise ValueError()
                if response.status_code != 200: raise ValueError()
        import json
        tokens = json.loads(body)
        if tokens.get("token_type", "").lower() != "bearer": raise ValueError()
        identity = await asyncio.to_thread(verifier.login, tokens["access_token"], tokens["id_token"], nonce_hash)
    except Exception:
        raise ApplicationError("AUTHENTICATION_REQUIRED") from None
    principal = resolve_identity(database, identity)
    opaque, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expiry = min(identity.expires_at, now+timedelta(seconds=settings.session_ttl_seconds))
    with database.session() as session, session.begin():
        session.add(AuthSession(id=uuid4(), user_id=principal.id, session_hash=digest(opaque), csrf_hash=digest(csrf), access_hash=digest(tokens["access_token"]),
            access_encrypted=seal(settings, tokens["access_token"]), created_at=now, expires_at=expiry, last_seen_at=now))
    return {"session": opaque, "csrf": csrf, "expires_at": expiry.isoformat()}


def session_record(database: Database, settings: Settings, opaque: str, *, touch: bool = False) -> AuthSession:
    now = datetime.now(UTC)
    if not 40 <= len(opaque) <= 100: raise ApplicationError("AUTHENTICATION_REQUIRED")
    with database.session() as session, session.begin():
        row = session.scalar(select(AuthSession).where(AuthSession.session_hash == digest(opaque)).with_for_update())
        if row is None or row.revoked_at or row.expires_at <= now or row.last_seen_at+timedelta(seconds=settings.session_idle_seconds) <= now:
            raise ApplicationError("AUTHENTICATION_REQUIRED")
        if touch: row.last_seen_at = now
        session.expunge(row)
        # Persist touch explicitly: expunging a dirty row would otherwise lose it.
        if touch: session.execute(update(AuthSession).where(AuthSession.id == row.id).values(last_seen_at=now))
        return row


def authenticate_session(database: Database, settings: Settings, verifier: OIDCVerifier, token: str, opaque: str, csrf: str | None, unsafe: bool) -> tuple[Principal, AuthSession]:
    identity = verifier.access(token)
    row = session_record(database, settings, opaque)
    if not compare_digest(row.access_hash, digest(token)) or unsafe and (csrf is None or not compare_digest(row.csrf_hash, digest(csrf))):
        raise ApplicationError("AUTHENTICATION_REQUIRED")
    with database.session() as session:
        external = session.scalar(select(ExternalIdentity).where(ExternalIdentity.issuer == identity.issuer, ExternalIdentity.subject == identity.subject, ExternalIdentity.user_id == row.user_id))
        user = session.get(User, row.user_id)
        if external is None or user is None: raise ApplicationError("AUTHENTICATION_REQUIRED")
        session_record(database, settings, opaque, touch=True)
        return Principal(id=user.id, display_name=user.display_name, identity_mode="oidc"), row


def revoke_session(database: Database, settings: Settings, opaque: str, csrf: str) -> None:
    row = session_record(database, settings, opaque)
    if not compare_digest(row.csrf_hash, digest(csrf)): raise ApplicationError("AUTHENTICATION_REQUIRED")
    with database.session() as session, session.begin():
        session.execute(update(AuthSession).where(AuthSession.id == row.id).values(revoked_at=datetime.now(UTC)))
