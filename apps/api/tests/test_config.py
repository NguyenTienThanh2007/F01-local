import pytest
from pathlib import Path
from typing import Any

from pydantic import SecretStr, ValidationError
from f01.config import Settings


def test_development_identity_cannot_run_in_production() -> None:
    with pytest.raises(ValidationError, match="cannot run in production"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://local/db",
            dev_api_token="x" * 32,
            _env_file=None,
        )


def test_sqlite_is_not_a_postgres_substitute() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(database_url="sqlite:///db", dev_api_token="x" * 32, _env_file=None)


def test_backend_environment_key_is_a_secret_and_not_part_of_settings_repr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=synthetic-file-credential\n", encoding="utf-8")
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://local/db",
        dev_api_token="x" * 32,
        _env_file=path,
    )
    assert isinstance(settings.openai_api_key, SecretStr)
    assert settings.openai_api_key.get_secret_value() == "synthetic-file-credential"
    assert "synthetic-file-credential" not in repr(settings)


def test_process_environment_has_precedence_over_backend_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=synthetic-file-credential\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-process-credential")
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://local/db",
        dev_api_token="x" * 32,
        _env_file=path,
    )
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "synthetic-process-credential"


def test_configuration_validation_does_not_echo_credentials() -> None:
    credential = "synthetic-private-credential"
    with pytest.raises(ValidationError) as failure:
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://local/db",
            dev_api_token="x" * 32,
            openai_api_key=SecretStr(credential),
            _env_file=None,
        )
    assert credential not in str(failure.value)


def test_production_oidc_requires_confidential_client_and_verified_email() -> None:
    from cryptography.fernet import Fernet
    from pydantic import ValidationError
    values: dict[str, Any] = dict(_env_file=None, app_env='production', auth_mode='oidc', database_url='postgresql+psycopg://f01:test@127.0.0.1/f01',
        auth_gateway_token='synthetic-'+'g'*32, session_encryption_key=Fernet.generate_key().decode(),
        oidc_issuer='https://identity.example.test/', oidc_authorization_url='https://identity.example.test/authorize',
        oidc_token_url='https://identity.example.test/token', oidc_jwks_url='https://identity.example.test/jwks',
        oidc_client_id='test-client', oidc_api_audience='test-api', oidc_redirect_uri='https://factory.example.test/api/auth/callback')
    with pytest.raises(ValidationError, match='confidential'):
        Settings(**values)
    with pytest.raises(ValidationError, match='verified email'):
        Settings(**values, oidc_client_secret='synthetic-private-client', oidc_require_verified_email=False)
    assert Settings(**values, oidc_client_secret='synthetic-private-client', oidc_google_connection='google-oauth2').auth_mode=='oidc'
