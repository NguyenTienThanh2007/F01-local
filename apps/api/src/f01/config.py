from functools import lru_cache
from datetime import datetime
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT.parents[1] / ".env", BACKEND_ROOT / ".env"),
        extra="ignore",
        hide_input_in_errors=True,
    )
    app_env: Literal["development", "test", "preview", "production"] = "development"
    auth_mode: Literal["development", "oidc"] = "development"
    execution_mode: Literal["simulated"] = "simulated"
    database_url: str
    dev_api_token: SecretStr = Field(default=SecretStr(""))
    auth_gateway_token: SecretStr = SecretStr("")
    session_encryption_key: SecretStr = SecretStr("")
    oidc_issuer: str = ""
    oidc_authorization_url: str = ""
    oidc_token_url: str = ""
    oidc_jwks_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: SecretStr = SecretStr("")
    oidc_api_audience: str = ""
    oidc_redirect_uri: str = ""
    session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    session_idle_seconds: int = Field(default=900, ge=60, le=3600)
    planning_requests_per_minute: int = Field(default=5, ge=1, le=30)
    planning_requests_per_day: int = Field(default=30, ge=1, le=1000)
    planning_daily_token_budget: int = Field(default=200000, ge=1000, le=10000000)
    planning_context_bytes: int = Field(default=24000, ge=4000, le=48000)
    planning_input_tokens: int = Field(default=28000, ge=4000, le=64000)
    planning_output_tokens: int = Field(default=3000, ge=256, le=6000)
    dev_auth_subject: str = Field(
        default="founder-development", min_length=1, max_length=200
    )
    openai_api_key: SecretStr | None = None
    planning_provider: Literal["openai"] = "openai"
    openai_model: str = Field(default="gpt-4.1-mini", min_length=1, max_length=100)
    planning_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    simulation_tick_ms: int = Field(default=1000, ge=100, le=10000)
    simulation_runner_enabled: bool = True
    simulation_change_scenario: Literal["auto", "recoverable-verification", "terminal-failure"] = "auto"
    dev_token_expires_at: datetime | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def private_identity_only(self) -> Self:
        if self.app_env == "production" and self.auth_mode == "development":
            raise ValueError("Development identity cannot run in production.")
        if self.auth_mode == "development" and len(self.dev_api_token.get_secret_value()) < 32:
            raise ValueError("Development credentials must be at least 32 characters.")
        if self.auth_mode == "oidc":
            if len(self.auth_gateway_token.get_secret_value()) < 32:
                raise ValueError("A private authentication gateway credential is required.")
            try:
                Fernet(self.session_encryption_key.get_secret_value().encode())
            except Exception:
                raise ValueError("A valid session encryption key is required.") from None
            if not self.oidc_client_id or not self.oidc_api_audience:
                raise ValueError("Configure the OIDC client and API audience.")
            for url in (self.oidc_issuer, self.oidc_authorization_url, self.oidc_token_url, self.oidc_jwks_url, self.oidc_redirect_uri):
                parsed = urlsplit(url)
                local_test = self.app_env in ("development", "test") and parsed.hostname in ("localhost", "127.0.0.1", "::1")
                if not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query or not (parsed.scheme == "https" or parsed.scheme == "http" and local_test):
                    raise ValueError("Identity endpoints must be fixed HTTPS URLs; loopback HTTP is local/test only.")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL with psycopg.")
        if self.simulation_change_scenario != "auto" and self.app_env not in ("development", "test"):
            raise ValueError("Failure fixtures are development/test configuration only.")
        if self.dev_token_expires_at is not None and self.dev_token_expires_at.tzinfo is None:
            raise ValueError("Development credential expiry must include a timezone.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
