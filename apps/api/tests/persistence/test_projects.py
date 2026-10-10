from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from f01.api.errors import ApplicationError
from f01.application import projects as service
from f01.config import Settings
from f01.db.models import (
    BrainRevision,
    BuildEvent,
    BuildRun,
    DeploymentRecord,
    IdempotencyKey,
    Project,
    ProjectRequest,
    ProjectVersion,
    User,
)
from f01.db.session import Database
from f01.domain.projects import CreateProject
from f01.main import create_app

BRIEF = "Build a CRM for a real estate agency with authentication, leads and notes."


def create(client: TestClient, key: str = "create-1", **body: object) -> dict[str, Any]:
    response = client.post(
        "/v1/projects", json={"brief": BRIEF, **body}, headers={"Idempotency-Key": key}
    )
    assert response.status_code == 201, response.json()
    assert (
        response.headers["Location"]
        == f"/v1/projects/{response.json()['project']['id']}"
    )
    return dict(response.json())


def test_atomic_creation_brain_snapshot_requests_and_restart(
    client: TestClient, project_settings: Settings, database: Database
) -> None:
    created = create(client, title="  Harbor CRM  ")
    project = created["project"]
    path = f"/v1/projects/{project['id']}"
    assert project["title"] == "Harbor CRM"
    assert project["event_sequence"] == project["status_event_sequence"] == 1
    snapshot = client.get(path + "/workspace").json()
    assert snapshot["last_sequence"] == snapshot["recent_events"][-1]["sequence"] == 1
    assert snapshot["active_run"]["status"] == "queued"
    assert snapshot["active_run"]["next_step_at"] is None
    assert (
        snapshot["current_version"] is None
        and snapshot["preview"]["status"] == "pending"
    )
    assert snapshot["current_brain"]["content"]["product"]["summary"]["text"] == BRIEF
    brain = client.get(path + "/brain").json()
    assert brain["context"]["requests"][0]["id"] == created["request_id"]
    assert client.get(path + "/requests").json()["items"][0]["text"] == BRIEF
    assert client.get(path + "/brain/revisions").json()["items"][0]["revision"] == 1
    assert client.get(path + "/brain?revision=2").status_code == 404
    with TestClient(create_app(project_settings)) as restarted:
        restarted.headers.update(client.headers)
        assert restarted.get(path).json() == project
        assert restarted.get(path + "/workspace").json() == snapshot
    with database.session() as session:
        for table in (
            Project,
            ProjectRequest,
            BrainRevision,
            BuildRun,
            BuildEvent,
            IdempotencyKey,
        ):
            assert session.scalar(select(func.count()).select_from(table)) == 1
        assert session.scalar(select(func.count()).select_from(ProjectVersion)) == 0


def test_ownership_and_identity_are_server_resolved(
    client: TestClient, project_settings: Settings
) -> None:
    created = create(client)
    project_id = created["project"]["id"]
    foreign_settings = project_settings.model_copy(
        update={"dev_auth_subject": "different-owner"}
    )
    with TestClient(create_app(foreign_settings)) as foreign:
        foreign.headers.update(client.headers)
        for suffix in ("", "/workspace", "/brain", "/brain/revisions", "/requests"):
            denied = foreign.get(f"/v1/projects/{project_id}{suffix}")
            missing = foreign.get(f"/v1/projects/{uuid4()}{suffix}")
            assert denied.status_code == missing.status_code == 404
            assert (
                denied.json()["error"]["message"] == missing.json()["error"]["message"]
            )
        assert (
            foreign.patch(
                f"/v1/projects/{project_id}",
                json={"title": "Steal"},
                headers={"If-Match": '"anything"'},
            ).status_code
            == 404
        )
        assert foreign.get("/v1/projects").json()["items"] == []
        another = create(foreign)
        assert (
            another["project"]["owner_user_id"] != created["project"]["owner_user_id"]
        )
    assert (
        client.get("/v1/session").json()["capabilities"]["simulation_runner"] is False
    )
    assert (
        client.get(
            "/v1/session", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/projects",
            json={"brief": BRIEF},
            headers={"Idempotency-Key": "another", "X-User-ID": str(uuid4())},
        ).json()["project"]["owner_user_id"]
        == created["project"]["owner_user_id"]
    )


def test_idempotency_replay_mismatch_expiry_and_concurrency(
    client: TestClient, database: Database, project_settings: Settings
) -> None:
    first = create(client)
    assert create(client) == first
    assert (
        client.post(
            "/v1/projects",
            json={"brief": BRIEF, "title": "Different"},
            headers={"Idempotency-Key": "create-1"},
        ).json()["error"]["code"]
        == "IDEMPOTENCY_KEY_REUSED"
    )
    with database.session() as session, session.begin():
        record = session.scalar(select(IdempotencyKey))
        assert record is not None
        record.created_at -= timedelta(days=2)
        record.expires_at -= timedelta(days=2)
    assert create(client)["project"]["id"] != first["project"]["id"]
    barrier = Barrier(8)

    def submit() -> dict[str, Any]:
        with TestClient(create_app(project_settings)) as worker:
            worker.headers.update(client.headers)
            barrier.wait(timeout=10)
            return create(worker, "concurrent")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: submit(), range(8)))
    assert all(item == results[0] for item in results)
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(Project)) == 3


def test_creation_failure_rolls_back_every_record_and_key(
    client: TestClient, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = service.append_event

    def fail(*args: object, **kwargs: object) -> None:
        raise ApplicationError("INTERNAL_ERROR")

    monkeypatch.setattr(service, "append_event", fail)
    result = client.post(
        "/v1/projects", json={"brief": BRIEF}, headers={"Idempotency-Key": "rollback"}
    )
    assert result.status_code == 500
    with database.session() as session:
        for table in (
            Project,
            ProjectRequest,
            BrainRevision,
            BuildRun,
            BuildEvent,
            IdempotencyKey,
        ):
            assert session.scalar(select(func.count()).select_from(table)) == 0
    monkeypatch.setattr(service, "append_event", original)
    assert create(client, "rollback")["project"]["event_sequence"] == 1


def test_idempotency_short_wait_returns_retryable_conflict(
    client: TestClient, project_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    reserved, release = Event(), Event()
    original = service._create_records

    def blocked(
        session: Session, owner: UUID, body: CreateProject, now: datetime
    ) -> Any:
        reserved.set()
        assert release.wait(10)
        return original(session, owner, body, now)

    monkeypatch.setattr(service, "_create_records", blocked)

    def first() -> dict[str, Any]:
        with TestClient(create_app(project_settings)) as worker:
            worker.headers.update(client.headers)
            return create(worker, "blocked")

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(first)
        assert reserved.wait(10)
        try:
            conflict = client.post(
                "/v1/projects",
                json={"brief": BRIEF},
                headers={"Idempotency-Key": "blocked"},
            )
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"
        finally:
            release.set()
        result = pending.result(timeout=10)
    assert create(client, "blocked") == result


def test_concurrent_metadata_updates_do_not_lose_writes(
    client: TestClient, project_settings: Settings
) -> None:
    created = create(client)
    path = f"/v1/projects/{created['project']['id']}"
    etag = client.get(path).headers["ETag"]
    barrier = Barrier(2)

    def rename(title: str) -> int:
        with TestClient(create_app(project_settings)) as worker:
            worker.headers.update(client.headers)
            barrier.wait(10)
            return int(
                worker.patch(
                    path, json={"title": title}, headers={"If-Match": etag}
                ).status_code
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(rename, ["First update", "Second update"]))
    assert sorted(codes) == [200, 412]
    assert client.get(path).json()["metadata_version"] == 2


def test_database_ready_checks_migration_compatibility(
    client: TestClient, database: Database
) -> None:
    assert client.get("/v1/health/ready").status_code == 200
    with database.engine.begin() as connection:
        original_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        connection.execute(
            text("UPDATE alembic_version SET version_num='incompatible'")
        )
    try:
        response = client.get("/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DATABASE_NOT_READY"
        assert client.get("/v1/health/live").status_code == 200
    finally:
        with database.engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num=:revision"), {"revision": original_revision}
            )
    assert client.get("/v1/health/ready").status_code == 200


def test_etags_rename_archive_unarchive_and_atomic_patch(
    client: TestClient, database: Database
) -> None:
    created = create(client)
    path = f"/v1/projects/{created['project']['id']}"
    etag = client.get(path).headers["ETag"]
    assert client.patch(path, json={"title": "New name"}).status_code == 428
    assert (
        client.patch(
            path, json={"title": "New name"}, headers={"If-Match": '"stale"'}
        ).status_code
        == 412
    )
    assert (
        client.patch(
            path,
            json={"title": "New name", "archived": True},
            headers={"If-Match": etag},
        ).status_code
        == 409
    )
    assert client.get(path).json()["title"] != "New name"
    renamed = client.patch(path, json={"title": "New name"}, headers={"If-Match": etag})
    assert renamed.status_code == 200 and renamed.headers["ETag"] != etag
    assert (
        client.patch(
            path, json={"title": "Lost update"}, headers={"If-Match": etag}
        ).status_code
        == 412
    )
    current_etag = renamed.headers["ETag"]
    # A fixture supplies a terminal run; M2 deliberately has no cancel command.
    with database.session() as session, session.begin():
        project = session.get(
            Project, UUID(created["project"]["id"]), with_for_update=True
        )
        run = session.get(BuildRun, UUID(created["run_id"]))
        assert project is not None and run is not None
        run.status = "canceled"
        run.finished_at = datetime.now(UTC)
        project.lifecycle = "idle"
        service.append_event(
            session,
            project,
            type="run.canceled",
            message="Test fixture cancellation.",
            actor=project.owner_user_id,
            run_id=run.id,
        )
    assert client.get(path).headers["ETag"] == current_etag
    archived = client.patch(
        path, json={"archived": True}, headers={"If-Match": current_etag}
    )
    assert archived.status_code == 200 and archived.json()["archived_at"] is not None
    assert client.get("/v1/projects").json()["items"] == []
    assert len(client.get("/v1/projects?archived=true").json()["items"]) == 1
    renamed_archive = client.patch(
        path,
        json={"title": "Archived name"},
        headers={"If-Match": archived.headers["ETag"]},
    )
    assert renamed_archive.status_code == 200
    unarchived = client.patch(
        path,
        json={"archived": False},
        headers={"If-Match": renamed_archive.headers["ETag"]},
    )
    assert unarchived.status_code == 200 and unarchived.json()["archived_at"] is None
    no_op = client.patch(
        path, json={"archived": False}, headers={"If-Match": unarchived.headers["ETag"]}
    )
    assert no_op.headers["ETag"] == unarchived.headers["ETag"]
    assert client.get(path + "/requests").json()["items"][0]["text"] == BRIEF


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"brief": "short"},
        {"brief": BRIEF, "mode": "real"},
        {"brief": BRIEF, "title": " "},
    ],
)
def test_create_validation_does_not_echo_input(
    client: TestClient, body: dict[str, object]
) -> None:
    response = client.post(
        "/v1/projects", json=body, headers={"Idempotency-Key": "validation"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert BRIEF not in response.text


def test_pagination_filters_and_validation(client: TestClient) -> None:
    for index in range(5):
        create(client, f"page-{index}", title=f"Project {index}")
    page = client.get("/v1/projects?limit=2").json()
    seen = list(page["items"])
    while page["next_cursor"]:
        page = client.get(
            "/v1/projects", params={"cursor": page["next_cursor"], "limit": 2}
        ).json()
        seen.extend(page["items"])
    assert len({item["id"] for item in seen}) == 5
    assert (
        len(
            client.get("/v1/projects?q=Project%201&status=understanding").json()[
                "items"
            ]
        )
        == 1
    )
    assert client.get("/v1/projects?q=%25").json()["items"] == []
    for query in ("limit=101", "limit=0", "cursor=bad", "status=made-up"):
        assert client.get("/v1/projects?" + query).status_code == 422
    assert client.post("/v1/projects", json={"brief": BRIEF}).status_code == 422
    path = f"/v1/projects/{seen[0]['id']}"
    for body in ({}, {"title": None}, {"archived": "false"}, {"lifecycle": "live"}):
        assert client.patch(path, json=body).status_code == 422


def test_snapshot_is_repeatable_during_concurrent_metadata_write(
    client: TestClient, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = create(client)
    path = f"/v1/projects/{created['project']['id']}"
    original = service.owned_project
    fetched, written = Event(), Event()

    def interleave(
        session: Session, owner: UUID, project_id: UUID, *, lock: bool = False
    ) -> Project:
        project = original(session, owner, project_id, lock=lock)
        if session.connection().get_isolation_level() == "REPEATABLE READ":
            fetched.set()
            assert written.wait(10)
        return project

    monkeypatch.setattr(service, "owned_project", interleave)
    etag = client.get(path).headers["ETag"]

    def rename() -> None:
        assert fetched.wait(10)
        result = client.patch(
            path, json={"title": "After snapshot"}, headers={"If-Match": etag}
        )
        assert result.status_code == 200
        written.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(rename)
        snapshot = client.get(path + "/workspace").json()
        pending.result(timeout=10)
    assert snapshot["last_sequence"] == 1
    assert len(snapshot["recent_events"]) == 1
    assert snapshot["project"]["title"] != "After snapshot"
    assert client.get(path).json()["event_sequence"] == 2


def test_creation_receipt_owner_assertion_prevents_session_switch_replay(
    client: TestClient, project_settings: Settings, database: Database
) -> None:
    owner = client.get("/v1/session").json()["principal"]["id"]
    headers = {"Idempotency-Key": "account-bound-create", "X-F01-Expected-Owner": owner}
    body = {"brief": BRIEF, "title": "Private recovery"}
    first = client.post("/v1/projects", json=body, headers=headers)
    assert first.status_code == 201
    foreign_settings = project_settings.model_copy(update={"dev_auth_subject": "switched-account"})
    with TestClient(create_app(foreign_settings)) as foreign:
        foreign.headers.update(client.headers)
        denied = foreign.post("/v1/projects", json=body, headers=headers)
        assert denied.status_code == 409
        assert denied.json()["error"]["code"] == "CREATION_ACCOUNT_CHANGED"
        assert foreign.get("/v1/projects").json()["items"] == []
    replay = client.post("/v1/projects", json=body, headers=headers)
    assert replay.json() == first.json()
    invalid = client.post("/v1/projects", json=body, headers={**headers, "X-F01-Expected-Owner": "bad"})
    assert invalid.status_code == 422
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(Project)) == 1
