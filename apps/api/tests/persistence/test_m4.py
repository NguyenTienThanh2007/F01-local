from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from f01.application import projects as service
from f01.config import Settings
from f01.db.models import BrainRevision, BuildEvent, BuildRun, IdempotencyKey, Project, ProjectRequest
from f01.db.session import Database
from f01.domain.projects import RecordChange
from f01.main import create_app
from .test_projects import create


def finish_fixture(database: Database, created: dict[str, Any]) -> None:
    # Disposable test setup, not an application runner or command.
    with database.session() as session, session.begin():
        run = session.get(BuildRun, UUID(created["run_id"]))
        project = session.get(Project, UUID(created["project"]["id"]))
        assert run and project
        run.status = "canceled"
        run.finished_at = datetime.now(UTC)
        project.lifecycle = "idle"


def body(created: dict[str, Any], **updates: object) -> dict[str, Any]:
    return {"text": "Add a filter for high priority leads.", "base_brain_revision_id": created["brain_revision_id"], "base_version_id": None, **updates}


def test_request_atomic_record_replay_and_original_brain_unchanged(client: TestClient, database: Database, project_settings: Settings) -> None:
    created = create(client)
    path = f"/v1/projects/{created['project']['id']}"
    initial = client.get(path + "/brain").json()["revision"]
    finish_fixture(database, created)
    response = client.post(path + "/requests", json=body(created), headers={"Idempotency-Key": "change"})
    assert response.status_code == 201, response.json()
    request = response.json()
    assert request["kind"] == "change"
    assert request["created_by"] == created["project"]["owner_user_id"]
    assert request["base_brain_revision_id"] == created["brain_revision_id"]
    assert client.post(path + "/requests", json=body(created), headers={"Idempotency-Key": "change"}).json() == request
    with TestClient(create_app(project_settings)) as restarted:
        restarted.headers.update(client.headers)
        assert restarted.get(path + "/requests").json()["items"][0] == request
    assert client.get(path + "/brain").json()["revision"] == initial
    assert len(client.get(path + "/brain").json()["context"]["requests"]) == 2
    snapshot = client.get(path + "/workspace").json()
    assert snapshot["active_run"] is None and snapshot["preview"]["status"] == "pending"
    assert snapshot["last_sequence"] == 2
    assert snapshot["project"]["metadata_version"] == 1
    events = client.get(path + "/events").json()["items"]
    assert [e["type"] for e in events] == ["project.created", "request.recorded"]
    assert events[-1]["request_id"] == request["id"] and events[-1]["mode"] is None
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(BrainRevision)) == 1
        assert session.scalar(select(func.count()).select_from(BuildRun)) == 1
        assert session.scalar(select(func.count()).select_from(ProjectRequest)) == 2


def test_active_archived_stale_and_validation_leave_no_records(client: TestClient, database: Database) -> None:
    created = create(client)
    path = f"/v1/projects/{created['project']['id']}"
    headers = {"Idempotency-Key": "attempt"}
    assert client.post(path + "/requests", json=body(created), headers=headers).json()["error"]["code"] == "ACTIVE_RUN_EXISTS"
    finish_fixture(database, created)
    for changes, code in [({"base_brain_revision_id": str(uuid4())}, "STALE_BRAIN_REVISION"), ({"base_version_id": str(uuid4())}, "STALE_BASE_VERSION")]:
        response = client.post(path + "/requests", json=body(created, **changes), headers=headers)
        assert response.status_code == 409 and response.json()["error"]["code"] == code
    validation_cases: list[dict[str, object]] = [{"text": " "}, {"text": "x" * 10001}, {"execute": True}, {"base_brain_revision_id": "not-an-id"}]
    for invalid in validation_cases:
        assert client.post(path + "/requests", json=body(created, **invalid), headers=headers).status_code == 422
    assert client.post(path + "/requests", json=body(created)).status_code == 422
    client.patch(path, json={"archived": True}, headers={"If-Match": client.get(path).headers["etag"]})
    assert client.post(path + "/requests", json=body(created), headers=headers).json()["error"]["code"] == "PROJECT_ARCHIVED"
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(ProjectRequest)) == 1
        assert session.scalar(select(func.count()).select_from(IdempotencyKey)) == 1


def test_change_replay_survives_context_change_and_mismatch_is_rejected(client: TestClient, database: Database) -> None:
    created = create(client); finish_fixture(database, created)
    path = f"/v1/projects/{created['project']['id']}"
    saved = client.post(path + "/requests", json=body(created), headers={"Idempotency-Key": "change"}).json()
    with database.session() as session, session.begin():
        original = session.get(BrainRevision, UUID(created["brain_revision_id"]))
        assert original
        next_revision = BrainRevision(id=uuid4(), project_id=original.project_id, revision=2, schema_version=1, source_request_id=UUID(saved["id"]), content=original.content, created_at=datetime.now(UTC))
        session.add(next_revision); session.flush()
        project = session.get(Project, original.project_id); assert project
        project.current_brain_revision_id = next_revision.id
    assert client.post(path + "/requests", json=body(created), headers={"Idempotency-Key": "change"}).json() == saved
    assert client.post(path + "/requests", json=body(created, text="Different change request for lead filtering"), headers={"Idempotency-Key": "change"}).json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert client.post(path + "/requests", json=body(created), headers={"Idempotency-Key": "new"}).json()["error"]["code"] == "STALE_BRAIN_REVISION"
    assert client.get(path + "/brain?revision=1").json()["revision"]["revision"] == 1
    assert client.get(path + "/brain").json()["revision"]["revision"] == 2


def test_concurrent_change_command_is_exactly_once(client: TestClient, database: Database) -> None:
    created = create(client); finish_fixture(database, created)
    project_id = UUID(created["project"]["id"]); owner = UUID(created["project"]["owner_user_id"])
    def record(_: int) -> UUID:
        return service.record_change(database, owner, project_id, RecordChange.model_validate(body(created)), "concurrent").id
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(record, range(4)))
    assert len(set(ids)) == 1
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(ProjectRequest)) == 2
        assert session.scalar(select(func.count()).select_from(BuildEvent)) == 2


def test_new_resources_remain_ownership_scoped(client: TestClient, database: Database, project_settings: Settings) -> None:
    created = create(client); finish_fixture(database, created)
    path = f"/v1/projects/{created['project']['id']}"
    with TestClient(create_app(project_settings.model_copy(update={"dev_auth_subject": "foreign"}))) as foreign:
        foreign.headers.update(client.headers)
        for suffix in ["/events", "/versions", f"/versions/{uuid4()}"]:
            assert foreign.get(path + suffix).status_code == 404
        assert foreign.post(path + "/requests", json=body(created), headers={"Idempotency-Key": "foreign"}).status_code == 404
    assert client.get(path + "/versions").json() == {"items": [], "next_cursor": None}
    assert client.get(path + f"/versions/{uuid4()}").status_code == 404


def test_event_history_is_sequence_ordered_and_paged(client: TestClient, database: Database) -> None:
    created = create(client); finish_fixture(database, created)
    path = f"/v1/projects/{created['project']['id']}"
    for n in range(3):
        assert client.post(path + "/requests", json=body(created, text=f"Record change number {n} for lead filtering"), headers={"Idempotency-Key": f"key{n}"}).status_code == 201
    page = client.get(path + "/events?limit=2").json()
    assert [e["sequence"] for e in page["items"]] == [1, 2] and page["next_cursor"] == "2"
    page = client.get(path + "/events?after_sequence=2&limit=2").json()
    assert [e["sequence"] for e in page["items"]] == [3, 4] and page["next_cursor"] is None
    assert client.get(path + "/events?after_sequence=5").status_code == 422
    assert client.get(path + "/events?after_sequence=-1").status_code == 422


def test_version_reads_and_required_current_version_context(client: TestClient, database: Database) -> None:
    from .test_constraints import fixture_output
    created = create(client)
    brain_id, version_id = fixture_output(database, created)
    path = f"/v1/projects/{created['project']['id']}"
    listing = client.get(path + "/versions").json()
    assert listing["next_cursor"] is None and len(listing["items"]) == 1
    assert listing["items"][0] == client.get(path + f"/versions/{version_id}").json()
    assert listing["items"][0]["preview_descriptor"]["fixture_id"] == "crm-v1"
    stale = client.post(path + "/requests", json=body(created, base_brain_revision_id=str(brain_id)), headers={"Idempotency-Key": "stale-version"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_BASE_VERSION"
    current = client.post(path + "/requests", json=body(created, base_brain_revision_id=str(brain_id), base_version_id=str(version_id)), headers={"Idempotency-Key": "current"})
    assert current.status_code == 201 and current.json()["base_version_id"] == str(version_id)
