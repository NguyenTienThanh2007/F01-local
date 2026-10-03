"""Disposable browser setup only. Never imported by application code."""
import json
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

from f01.db.session import Database
from f01.application.runs import start_run
from f01.domain.projects import StartRun
from f01.db.models import BrainRevision, BuildRun, Project, ProjectVersion
from tests.persistence.test_constraints import fixture_output
from tests.persistence.test_m4 import finish_fixture

if __name__ == "__main__":
    url, action = sys.argv[1:3]
    created = json.load(sys.stdin)
    database = Database(url)
    try:
        if action == "recoverable-run":
            if '/f01_test_' not in url:
                raise ValueError('Fixture commands require a disposable test database')
            with database.session() as session:
                project = session.get(Project, UUID(created['project']['id']))
                assert project is not None
                owner, brain, project_id = project.owner_user_id, project.current_brain_revision_id, project.id
            configured_run = start_run(database, owner, project_id, StartRun(request_id=UUID(created['request_id']), expected_brain_revision_id=brain), str(uuid4()), change_scenario='recoverable-verification')
            print(configured_run.model_dump_json())
        elif action == "finish":
            finish_fixture(database, created)
        elif action == "output":
            brain_id, version_id = fixture_output(database, created)
            print(json.dumps({"brain": str(brain_id), "version": str(version_id)}))
        elif action == "version":
            with database.session() as session, session.begin():
                project = session.get(Project, UUID(created["project"]["id"]), with_for_update=True)
                assert project
                run_row = session.get(BuildRun, UUID(created["run_id"]))
                assert run_row
                values = {column.name: getattr(run_row, column.name) for column in BuildRun.__table__.columns}
                now = datetime.now(UTC)
                values.update(id=uuid4(), attempt=2, input_brain_revision_id=project.current_brain_revision_id, base_version_id=project.current_version_id, created_at=now, started_at=now, finished_at=now)
                run = BuildRun(**values); session.add(run); session.flush()
                version_row = ProjectVersion(id=uuid4(), project_id=project.id, number=2, run_id=run.id, brain_revision_id=project.current_brain_revision_id, mode="simulated", summary="Second metadata-only browser fixture.", preview_descriptor={"kind": "fixture", "fixture_id": "generic-v1"}, created_at=now)
                session.add(version_row); session.flush()
                project.current_version_id = version_row.id
                print(json.dumps({"version": str(version_row.id)}))
        elif action in ("brain", "unknown-schema"):
            with database.session() as session, session.begin():
                project = session.get(Project, UUID(created["project"]["id"]), with_for_update=True)
                assert project
                prior_brain = session.get(BrainRevision, project.current_brain_revision_id)
                assert prior_brain
                revision = BrainRevision(id=uuid4(), project_id=project.id, revision=prior_brain.revision + 1, schema_version=2 if action == "unknown-schema" else 1, source_request_id=UUID(created["request_id"]), content=prior_brain.content, created_at=datetime.now(UTC))
                session.add(revision); session.flush()
                project.current_brain_revision_id = revision.id
                print(json.dumps({"brain": str(revision.id)}))
        else:
            raise ValueError("Unsupported fixture action")
    finally:
        database.close()
