import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from f01.config import Settings
from f01.db.session import Database
from f01.main import create_app


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "Set TEST_DATABASE_URL to a disposable PostgreSQL database named f01_test_*. Persistence tests never use DATABASE_URL."
        )
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg" or not (
        parsed.database or ""
    ).startswith("f01_test_"):
        pytest.fail(
            "Persistence tests require a disposable f01_test_* PostgreSQL database."
        )
    engine = create_engine(url, hide_parameters=True)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        assert len(inspect(connection).get_table_names()) == 20
        command.downgrade(config, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        assert len(inspect(connection).get_table_names()) == 20
        command.check(config)
    engine.dispose()
    return url


@pytest.fixture
def database(database_url: str) -> Iterator[Database]:
    database = Database(database_url)
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, projects, project_requests, brain_revisions, build_runs, build_events, project_versions, deployment_records, idempotency_keys CASCADE"
            )
        )
    yield database
    database.close()


@pytest.fixture
def project_settings(
    settings: Settings, database: Database, database_url: str
) -> Settings:
    return settings.model_copy(update={"database_url": database_url})


@pytest.fixture
def db_session(database: Database) -> Iterator[Session]:
    with database.session() as session:
        yield session


@pytest.fixture
def client(project_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(project_settings)) as client:
        client.headers["Authorization"] = (
            f"Bearer {project_settings.dev_api_token.get_secret_value()}"
        )
        yield client
