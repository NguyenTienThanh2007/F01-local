from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError

from f01.db.models import (
    BrainRevision,
    BuildEvent,
    BuildRun,
    DeploymentRecord,
    IdempotencyKey,
    Project,
    ProjectRequest,
    ProjectVersion,
)
from f01.db.session import Database
from tests.persistence.test_projects import create


@pytest.fixture
def pair(client: TestClient) -> tuple[dict[str, Any], dict[str, Any]]:
    return create(client, "first"), create(client, "second")


def run_values(created: dict[str, Any]) -> dict[str, object]:
    return dict(
        id=uuid4(),
        project_id=UUID(created["project"]["id"]),
        request_id=UUID(created["request_id"]),
        input_brain_revision_id=UUID(created["brain_revision_id"]),
        attempt=2,
        mode="simulated",
        status="queued",
        scenario_id="generic-success",
        scenario_version=1,
        step_cursor=0,
        created_at=datetime.now(UTC),
    )


def assert_foreign_key(error: IntegrityError, constraint: str) -> None:
    assert isinstance(error.orig, ForeignKeyViolation)
    assert error.orig.diag.constraint_name == constraint


def test_active_run_unique_and_archive_guards(
    pair: tuple[dict[str, Any], dict[str, Any]], database: Database
) -> None:
    first, _ = pair
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(insert(BuildRun).values(**run_values(first)))
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(
            text("UPDATE projects SET archived_at=now() WHERE id=:id"),
            {"id": first["project"]["id"]},
        )
    with database.session() as session, session.begin():
        project = session.get(
            Project, UUID(first["project"]["id"]), with_for_update=True
        )
        assert project is not None
        session.execute(
            text(
                "UPDATE build_runs SET status='canceled', finished_at=now() WHERE id=:id"
            ),
            {"id": first["run_id"]},
        )
        project.archived_at = datetime.now(UTC)
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(insert(BuildRun).values(**run_values(first)))
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(
            text(
                "UPDATE build_runs SET status='running',phase='understanding',started_at=now(),finished_at=NULL WHERE id=:id"
            ),
            {"id": first["run_id"]},
        )


@pytest.mark.parametrize(
    "table,id_field",
    [
        ("brain_revisions", "brain_revision_id"),
        ("project_requests", "request_id"),
        ("build_events", None),
    ],
)
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_history_is_immutable_in_postgresql(
    pair: tuple[dict[str, Any], dict[str, Any]],
    database: Database,
    table: str,
    id_field: str | None,
    operation: str,
) -> None:
    first, _ = pair
    identifier = first[id_field] if id_field else None
    with database.session() as session:
        if identifier is None:
            identifier = session.scalar(
                select(BuildEvent.id).where(
                    BuildEvent.project_id == UUID(first["project"]["id"])
                )
            )
    assignment = {
        "brain_revisions": "schema_version=schema_version",
        "project_requests": "text=text",
        "build_events": "message=message",
    }[table]
    query = (
        f"UPDATE {table} SET {assignment} WHERE id=:id"
        if operation == "UPDATE"
        else f"DELETE FROM {table} WHERE id=:id"
    )
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(text(query), {"id": identifier})


@pytest.mark.parametrize(
    "field,foreign_field",
    [
        ("request_id", "request_id"),
        ("input_brain_revision_id", "brain_revision_id"),
        ("retry_of_run_id", "run_id"),
    ],
)
def test_run_cross_project_inputs_are_rejected(
    pair: tuple[dict[str, Any], dict[str, Any]],
    database: Database,
    field: str,
    foreign_field: str,
) -> None:
    first, second = pair
    values = run_values(first)
    values.update(status="canceled", finished_at=datetime.now(UTC))
    values[field] = UUID(second[foreign_field])
    with (
        pytest.raises(IntegrityError) as rejected,
        database.session() as session,
        session.begin(),
    ):
        session.execute(insert(BuildRun).values(**values))
    target = {
        "request_id": "project_requests",
        "input_brain_revision_id": "brain_revisions",
        "retry_of_run_id": "build_runs",
    }[field]
    assert_foreign_key(rejected.value, f"fk_{field}_{target}")


@pytest.mark.parametrize(
    "field,foreign_field",
    [("source_request_id", "request_id"), ("source_run_id", "run_id")],
)
def test_brain_cross_project_sources_are_rejected(
    pair: tuple[dict[str, Any], dict[str, Any]],
    database: Database,
    field: str,
    foreign_field: str,
) -> None:
    first, second = pair
    with database.session() as session:
        original = session.get(BrainRevision, UUID(first["brain_revision_id"]))
        assert original is not None
        values = dict(
            id=uuid4(),
            project_id=original.project_id,
            revision=2,
            schema_version=1,
            source_request_id=original.source_request_id,
            source_run_id=None,
            content=original.content,
            created_at=datetime.now(UTC),
        )
    values[field] = UUID(second[foreign_field])
    with (
        pytest.raises(IntegrityError) as rejected,
        database.session() as session,
        session.begin(),
    ):
        session.execute(insert(BrainRevision).values(**values))
    target = "project_requests" if field == "source_request_id" else "build_runs"
    assert_foreign_key(rejected.value, f"fk_{field}_{target}")


@pytest.mark.parametrize(
    "field,foreign_field", [("run_id", "run_id"), ("request_id", "request_id")]
)
def test_event_cross_project_references_are_rejected(
    pair: tuple[dict[str, Any], dict[str, Any]],
    database: Database,
    field: str,
    foreign_field: str,
) -> None:
    first, second = pair
    values: dict[str, object] = dict(
        id=uuid4(),
        project_id=UUID(first["project"]["id"]),
        sequence=2,
        type="step.completed",
        severity="info",
        message="Fixture event.",
        payload={},
        occurred_at=datetime.now(UTC),
    )
    values[field] = UUID(second[foreign_field])
    with (
        pytest.raises(IntegrityError) as rejected,
        database.session() as session,
        session.begin(),
    ):
        session.execute(insert(BuildEvent).values(**values))
    target = "build_runs" if field == "run_id" else "project_requests"
    assert_foreign_key(rejected.value, f"fk_{field}_{target}")


def test_project_pointer_and_request_owner_cross_project_guards(
    pair: tuple[dict[str, Any], dict[str, Any]], database: Database
) -> None:
    first, second = pair
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(
            text("UPDATE projects SET current_brain_revision_id=:brain WHERE id=:id"),
            {"brain": second["brain_revision_id"], "id": first["project"]["id"]},
        )
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(
            insert(ProjectRequest).values(
                id=uuid4(),
                project_id=UUID(first["project"]["id"]),
                created_by=uuid4(),
                kind="change",
                text="Change the project navigation layout.",
                base_brain_revision_id=UUID(first["brain_revision_id"]),
                created_at=datetime.now(UTC),
            )
        )
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(
            insert(ProjectRequest).values(
                id=uuid4(),
                project_id=UUID(first["project"]["id"]),
                created_by=UUID(first["project"]["owner_user_id"]),
                kind="change",
                text="Change the project navigation layout.",
                base_brain_revision_id=UUID(second["brain_revision_id"]),
                created_at=datetime.now(UTC),
            )
        )


def fixture_output(database: Database, created: dict[str, Any]) -> tuple[UUID, UUID]:
    now = datetime.now(UTC)
    brain_id, version_id = uuid4(), uuid4()
    with database.session() as session, session.begin():
        project = session.get(
            Project, UUID(created["project"]["id"]), with_for_update=True
        )
        original = session.get(BrainRevision, UUID(created["brain_revision_id"]))
        assert project is not None and original is not None
        session.execute(
            text(
                "UPDATE build_runs SET status='running', phase='understanding', started_at=now() WHERE id=:id"
            ),
            {"id": created["run_id"]},
        )
        session.execute(
            text(
                "UPDATE build_runs SET status='succeeded', phase='deploying', finished_at=now() WHERE id=:id"
            ),
            {"id": created["run_id"]},
        )
        session.execute(
            insert(BrainRevision).values(
                id=brain_id,
                project_id=project.id,
                revision=2,
                schema_version=1,
                source_request_id=UUID(created["request_id"]),
                source_run_id=UUID(created["run_id"]),
                content=original.content,
                created_at=now,
            )
        )
        session.execute(
            insert(ProjectVersion).values(
                id=version_id,
                project_id=project.id,
                number=1,
                run_id=UUID(created["run_id"]),
                brain_revision_id=brain_id,
                mode="simulated",
                summary="Metadata-only test fixture.",
                preview_descriptor={
                    "kind": "fixture",
                    "fixture_id": "crm-v1",
                },
                created_at=now,
            )
        )
        project.current_brain_revision_id = brain_id
        project.current_version_id = version_id
        project.lifecycle = "live"
    return brain_id, version_id


@pytest.mark.parametrize(
    "reference",
    [
        "project_current_version",
        "request_base_version",
        "run_base_version",
        "version_run",
        "version_brain",
        "deployment_run",
        "deployment_version",
    ],
)
def test_version_and_deployment_cross_project_references(
    pair: tuple[dict[str, Any], dict[str, Any]], database: Database, reference: str
) -> None:
    first, second = pair
    brain1, version1 = fixture_output(database, first)
    if reference == "version_run":
        brain2, version2 = UUID(second["brain_revision_id"]), uuid4()
    else:
        brain2, version2 = fixture_output(database, second)
    pid, owner, run1 = (
        UUID(first["project"]["id"]),
        UUID(first["project"]["owner_user_id"]),
        UUID(first["run_id"]),
    )
    now = datetime.now(UTC)
    available_run_id = uuid4()
    if reference == "version_brain":
        values = run_values(first)
        values.update(id=available_run_id, status="canceled", finished_at=now)
        with database.session() as session, session.begin():
            session.execute(insert(BuildRun).values(**values))
    with (
        pytest.raises(IntegrityError) as rejected,
        database.session() as session,
        session.begin(),
    ):
        if reference == "project_current_version":
            session.execute(
                text("UPDATE projects SET current_version_id=:version WHERE id=:id"),
                {"version": version2, "id": pid},
            )
        elif reference == "request_base_version":
            session.execute(
                insert(ProjectRequest).values(
                    id=uuid4(),
                    project_id=pid,
                    created_by=owner,
                    kind="change",
                    text="Change the navigation and typography.",
                    base_brain_revision_id=brain1,
                    base_version_id=version2,
                    created_at=now,
                )
            )
        elif reference == "run_base_version":
            values = run_values(first)
            values.update(status="canceled", finished_at=now, base_version_id=version2)
            session.execute(insert(BuildRun).values(**values))
        elif reference.startswith("version_"):
            session.execute(
                insert(ProjectVersion).values(
                    id=uuid4(),
                    project_id=pid,
                    number=2,
                    run_id=UUID(second["run_id"])
                    if reference == "version_run"
                    else available_run_id,
                    brain_revision_id=brain2
                    if reference == "version_brain"
                    else brain1,
                    mode="simulated",
                    summary="Invalid fixture.",
                    preview_descriptor={},
                    created_at=now,
                )
            )
        else:
            session.execute(
                insert(DeploymentRecord).values(
                    id=uuid4(),
                    project_id=pid,
                    version_id=version2
                    if reference == "deployment_version"
                    else version1,
                    run_id=UUID(second["run_id"])
                    if reference == "deployment_run"
                    else run1,
                    mode="simulated",
                    target="internal_fixture",
                    status="succeeded",
                    created_at=now,
                    completed_at=now,
                )
            )
    expected = {
        "project_current_version": "fk_project_current_version",
        "request_base_version": "fk_base_version_id_project_versions",
        "run_base_version": "fk_base_version_id_project_versions",
        "version_run": "fk_run_id_build_runs",
        "version_brain": "fk_brain_revision_id_brain_revisions",
        "deployment_run": "fk_run_id_build_runs",
        "deployment_version": "fk_version_id_project_versions",
    }
    assert_foreign_key(rejected.value, expected[reference])


def test_success_output_uniqueness_version_immutability_and_read_context(
    pair: tuple[dict[str, Any], dict[str, Any]], database: Database, client: TestClient
) -> None:
    first, _ = pair
    brain_id, version_id = fixture_output(database, first)
    path = f"/v1/projects/{first['project']['id']}"
    assert (
        client.get(path + "/brain?revision=1").json()["revision"]["id"]
        == first["brain_revision_id"]
    )
    assert client.get(path + "/brain").json()["revision"]["id"] == str(brain_id)
    assert client.get(path + "/workspace").json()["preview"]["status"] == "available"
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(
            text("UPDATE project_versions SET summary='replacement' WHERE id=:id"),
            {"id": version_id},
        )
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(
            text("DELETE FROM project_versions WHERE id=:id"), {"id": version_id}
        )
    with database.session() as session:
        brain = session.get(BrainRevision, brain_id)
        assert brain is not None
        brain_values = dict(
            id=uuid4(),
            project_id=brain.project_id,
            revision=3,
            schema_version=1,
            source_request_id=brain.source_request_id,
            source_run_id=brain.source_run_id,
            content=brain.content,
            created_at=datetime.now(UTC),
        )
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(insert(BrainRevision).values(**brain_values))
    with database.session() as session:
        version = session.get(ProjectVersion, version_id)
        assert version is not None
        version_values = {
            column.name: getattr(version, column.name)
            for column in ProjectVersion.__table__.columns
        }
    version_values.update(id=uuid4(), number=2)
    with (
        pytest.raises(IntegrityError) as duplicate,
        database.session() as session,
        session.begin(),
    ):
        session.execute(insert(ProjectVersion).values(**version_values))
    assert isinstance(duplicate.value.orig, UniqueViolation)
    assert duplicate.value.orig.diag.constraint_name == "uq_project_versions_run_id"
    deployment_values = dict(
        id=uuid4(),
        project_id=UUID(first["project"]["id"]),
        version_id=version_id,
        run_id=UUID(first["run_id"]),
        mode="simulated",
        target="internal_fixture",
        status="succeeded",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    with database.session() as session, session.begin():
        session.execute(insert(DeploymentRecord).values(**deployment_values))
    deployment_values["id"] = uuid4()
    with (
        pytest.raises(IntegrityError) as duplicate,
        database.session() as session,
        session.begin(),
    ):
        session.execute(insert(DeploymentRecord).values(**deployment_values))
    assert isinstance(duplicate.value.orig, UniqueViolation)
    assert duplicate.value.orig.diag.constraint_name == "uq_deployment_records_run_id"


def test_current_brain_is_required_and_incomplete_idempotency_cannot_commit(
    pair: tuple[dict[str, Any], dict[str, Any]], database: Database
) -> None:
    first, _ = pair
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(
            text("UPDATE projects SET current_brain_revision_id=NULL WHERE id=:id"),
            {"id": first["project"]["id"]},
        )
    with database.session() as session:
        original = session.scalar(select(IdempotencyKey))
        assert original is not None
        values = {
            column.name: getattr(original, column.name)
            for column in IdempotencyKey.__table__.columns
        }
    values.update(id=uuid4(), key="incomplete", response_status=0, response_body={})
    with pytest.raises(IntegrityError), database.session() as session, session.begin():
        session.execute(insert(IdempotencyKey).values(**values))


def test_unsupported_brain_schema_is_explicit(
    pair: tuple[dict[str, Any], dict[str, Any]], database: Database, client: TestClient
) -> None:
    first, _ = pair
    new_id = uuid4()
    path = f"/v1/projects/{first['project']['id']}"
    with database.session() as session, session.begin():
        project = session.get(
            Project, UUID(first["project"]["id"]), with_for_update=True
        )
        assert project is not None
        session.execute(
            insert(BrainRevision).values(
                id=new_id,
                project_id=project.id,
                revision=2,
                schema_version=99,
                source_request_id=UUID(first["request_id"]),
                content={},
                created_at=datetime.now(UTC),
            )
        )
        project.current_brain_revision_id = new_id
    for suffix in ("/brain", "/workspace"):
        response = client.get(path + suffix)
        assert (
            response.status_code == 409
            and response.json()["error"]["code"] == "UNSUPPORTED_BRAIN_SCHEMA"
        )
    assert client.get(path + "/brain?revision=1").status_code == 200
