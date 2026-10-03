"""Phase 1 domain. Frozen DDL; never import evolving ORM metadata here."""

from alembic import op

revision = "0001_phase1"
down_revision = None
branch_labels = None
depends_on = None

DDL = (
    """
CREATE TABLE users (
	id UUID NOT NULL, 
	identity_issuer VARCHAR(100) NOT NULL, 
	identity_subject VARCHAR(200) NOT NULL, 
	display_name VARCHAR(100) NOT NULL, 
	email VARCHAR(320), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (id), 
	CONSTRAINT uq_users_identity_issuer_identity_subject UNIQUE (identity_issuer, identity_subject)
)
    """,
    """
CREATE TABLE projects (
	id UUID NOT NULL, 
	owner_user_id UUID NOT NULL, 
	title VARCHAR(100) NOT NULL, 
	lifecycle VARCHAR(20) NOT NULL, 
	current_brain_revision_id UUID NOT NULL, 
	current_version_id UUID, 
	metadata_version INTEGER NOT NULL, 
	event_sequence INTEGER NOT NULL, 
	status_event_sequence INTEGER NOT NULL, 
	last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	archived_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_projects PRIMARY KEY (id), 
	CONSTRAINT uq_projects_id_owner_user_id UNIQUE (id, owner_user_id), 
	CONSTRAINT ck_projects_title CHECK (length(btrim(title)) BETWEEN 1 AND 100), 
	CONSTRAINT ck_projects_lifecycle CHECK (lifecycle IN ('idle','understanding','planning','building','verifying','deploying','live','error')), 
	CONSTRAINT ck_projects_counters CHECK (metadata_version > 0 AND event_sequence >= 0 AND status_event_sequence >= 0 AND status_event_sequence <= event_sequence)
)
    """,
    """
CREATE TABLE project_requests (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	created_by UUID NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	text TEXT NOT NULL, 
	base_brain_revision_id UUID, 
	base_version_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_project_requests PRIMARY KEY (id), 
	CONSTRAINT uq_project_requests_project_id_id UNIQUE (project_id, id), 
	CONSTRAINT ck_project_requests_kind_and_base CHECK ((kind = 'initial' AND base_brain_revision_id IS NULL AND base_version_id IS NULL) OR (kind = 'change' AND base_brain_revision_id IS NOT NULL)), 
	CONSTRAINT ck_project_requests_text CHECK (length(btrim(text)) BETWEEN 20 AND 10000)
)
    """,
    """
CREATE TABLE brain_revisions (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	revision INTEGER NOT NULL, 
	schema_version INTEGER NOT NULL, 
	source_request_id UUID NOT NULL, 
	source_run_id UUID, 
	content JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_brain_revisions PRIMARY KEY (id), 
	CONSTRAINT uq_brain_revisions_project_id_id UNIQUE (project_id, id), 
	CONSTRAINT uq_brain_revisions_project_id_revision UNIQUE (project_id, revision), 
	CONSTRAINT uq_brain_revisions_source_run_id UNIQUE (source_run_id), 
	CONSTRAINT ck_brain_revisions_schema CHECK (revision > 0 AND schema_version > 0 AND jsonb_typeof(content) = 'object')
)
    """,
    """
CREATE TABLE build_runs (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	request_id UUID NOT NULL, 
	input_brain_revision_id UUID NOT NULL, 
	base_version_id UUID, 
	retry_of_run_id UUID, 
	attempt INTEGER NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	phase VARCHAR(20), 
	scenario_id VARCHAR(100) NOT NULL, 
	scenario_version INTEGER NOT NULL, 
	step_cursor INTEGER NOT NULL, 
	next_step_at TIMESTAMP WITH TIME ZONE, 
	last_heartbeat_at TIMESTAMP WITH TIME ZONE, 
	error_code VARCHAR(100), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_build_runs PRIMARY KEY (id), 
	CONSTRAINT uq_build_runs_project_id_id UNIQUE (project_id, id), 
	CONSTRAINT ck_build_runs_mode CHECK (mode = 'simulated'), 
	CONSTRAINT ck_build_runs_status CHECK (status IN ('queued','running','succeeded','failed','canceled')), 
	CONSTRAINT ck_build_runs_phase CHECK (phase IS NULL OR phase IN ('understanding','planning','building','verifying','deploying')), 
	CONSTRAINT ck_build_runs_counters CHECK (attempt > 0 AND scenario_version > 0 AND step_cursor >= 0), 
	CONSTRAINT ck_build_runs_timing CHECK ((status = 'queued' AND phase IS NULL AND started_at IS NULL AND finished_at IS NULL) OR (status = 'running' AND phase IS NOT NULL AND started_at IS NOT NULL AND finished_at IS NULL) OR (status IN ('succeeded','failed','canceled') AND finished_at IS NOT NULL))
)
    """,
    """
CREATE TABLE build_events (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	run_id UUID, 
	request_id UUID, 
	sequence INTEGER NOT NULL, 
	deduplication_key VARCHAR(200), 
	type VARCHAR(100) NOT NULL, 
	phase VARCHAR(20), 
	severity VARCHAR(20) NOT NULL, 
	message VARCHAR(1000) NOT NULL, 
	mode VARCHAR(20), 
	payload JSONB NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_build_events PRIMARY KEY (id), 
	CONSTRAINT uq_build_events_project_id_id UNIQUE (project_id, id), 
	CONSTRAINT uq_build_events_project_id_sequence UNIQUE (project_id, sequence), 
	CONSTRAINT uq_build_events_project_id_deduplication_key UNIQUE (project_id, deduplication_key), 
	CONSTRAINT ck_build_events_payload CHECK (sequence > 0 AND jsonb_typeof(payload) = 'object'), 
	CONSTRAINT ck_build_events_severity CHECK (severity IN ('info','warning','error')), 
	CONSTRAINT ck_build_events_mode CHECK (mode IS NULL OR mode = 'simulated'), 
	CONSTRAINT ck_build_events_phase CHECK (phase IS NULL OR phase IN ('understanding','planning','building','verifying','deploying'))
)
    """,
    """
CREATE TABLE project_versions (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	number INTEGER NOT NULL, 
	run_id UUID NOT NULL, 
	brain_revision_id UUID NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	summary VARCHAR(1000) NOT NULL, 
	preview_descriptor JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_project_versions PRIMARY KEY (id), 
	CONSTRAINT uq_project_versions_project_id_id UNIQUE (project_id, id), 
	CONSTRAINT uq_project_versions_project_id_number UNIQUE (project_id, number), 
	CONSTRAINT uq_project_versions_run_id UNIQUE (run_id), 
	CONSTRAINT ck_project_versions_output CHECK (number > 0 AND mode = 'simulated' AND jsonb_typeof(preview_descriptor) = 'object')
)
    """,
    """
CREATE TABLE deployment_records (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	version_id UUID NOT NULL, 
	run_id UUID NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	target VARCHAR(40) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	external_url TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_deployment_records PRIMARY KEY (id), 
	CONSTRAINT uq_deployment_records_project_id_id UNIQUE (project_id, id), 
	CONSTRAINT uq_deployment_records_run_id UNIQUE (run_id), 
	CONSTRAINT ck_deployment_records_simulated CHECK (mode = 'simulated' AND target = 'internal_fixture' AND external_url IS NULL), 
	CONSTRAINT ck_deployment_records_status CHECK (status IN ('pending','succeeded','failed'))
)
    """,
    """
CREATE TABLE idempotency_keys (
	id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	method VARCHAR(10) NOT NULL, 
	route_scope VARCHAR(200) NOT NULL, 
	key VARCHAR(200) NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	response_status INTEGER NOT NULL, 
	response_body JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_idempotency_keys PRIMARY KEY (id), 
	CONSTRAINT uq_idempotency_keys_user_id_method_route_scope_key UNIQUE (user_id, method, route_scope, key), 
	CONSTRAINT ck_idempotency_keys_response_status CHECK (response_status = 0 OR response_status BETWEEN 100 AND 599), 
	CONSTRAINT ck_idempotency_keys_response CHECK (expires_at > created_at AND jsonb_typeof(response_body) = 'object')
)
    """,
    """
ALTER TABLE projects ADD CONSTRAINT fk_project_current_brain FOREIGN KEY(id, current_brain_revision_id) REFERENCES brain_revisions (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE projects ADD CONSTRAINT fk_project_current_version FOREIGN KEY(id, current_version_id) REFERENCES project_versions (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE projects ADD CONSTRAINT fk_projects_owner_user_id_users FOREIGN KEY(owner_user_id) REFERENCES users (id)
    """,
    """
CREATE INDEX ix_projects_owner_listing ON projects (owner_user_id, archived_at, updated_at, id)
    """,
    """
ALTER TABLE project_requests ADD CONSTRAINT fk_base_brain_revision_id_brain_revisions FOREIGN KEY(project_id, base_brain_revision_id) REFERENCES brain_revisions (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE project_requests ADD CONSTRAINT fk_base_version_id_project_versions FOREIGN KEY(project_id, base_version_id) REFERENCES project_versions (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE project_requests ADD CONSTRAINT fk_project_requests_created_by_users FOREIGN KEY(created_by) REFERENCES users (id)
    """,
    """
ALTER TABLE project_requests ADD CONSTRAINT fk_project_requests_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)
    """,
    """
ALTER TABLE project_requests ADD CONSTRAINT fk_request_owner FOREIGN KEY(project_id, created_by) REFERENCES projects (id, owner_user_id)
    """,
    """
CREATE INDEX ix_requests_history ON project_requests (project_id, created_at, id)
    """,
    """
ALTER TABLE brain_revisions ADD CONSTRAINT fk_brain_revisions_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)
    """,
    """
ALTER TABLE brain_revisions ADD CONSTRAINT fk_source_request_id_project_requests FOREIGN KEY(project_id, source_request_id) REFERENCES project_requests (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE brain_revisions ADD CONSTRAINT fk_source_run_id_build_runs FOREIGN KEY(project_id, source_run_id) REFERENCES build_runs (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE build_runs ADD CONSTRAINT fk_base_version_id_project_versions FOREIGN KEY(project_id, base_version_id) REFERENCES project_versions (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE build_runs ADD CONSTRAINT fk_build_runs_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)
    """,
    """
ALTER TABLE build_runs ADD CONSTRAINT fk_input_brain_revision_id_brain_revisions FOREIGN KEY(project_id, input_brain_revision_id) REFERENCES brain_revisions (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE build_runs ADD CONSTRAINT fk_request_id_project_requests FOREIGN KEY(project_id, request_id) REFERENCES project_requests (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE build_runs ADD CONSTRAINT fk_retry_of_run_id_build_runs FOREIGN KEY(project_id, retry_of_run_id) REFERENCES build_runs (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
CREATE INDEX ix_runs_history ON build_runs (project_id, created_at, id)
    """,
    """
CREATE UNIQUE INDEX uq_runs_one_active ON build_runs (project_id) WHERE status IN ('queued','running')
    """,
    """
ALTER TABLE build_events ADD CONSTRAINT fk_build_events_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)
    """,
    """
ALTER TABLE build_events ADD CONSTRAINT fk_request_id_project_requests FOREIGN KEY(project_id, request_id) REFERENCES project_requests (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE build_events ADD CONSTRAINT fk_run_id_build_runs FOREIGN KEY(project_id, run_id) REFERENCES build_runs (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
CREATE INDEX ix_events_run_sequence ON build_events (run_id, sequence)
    """,
    """
ALTER TABLE project_versions ADD CONSTRAINT fk_brain_revision_id_brain_revisions FOREIGN KEY(project_id, brain_revision_id) REFERENCES brain_revisions (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE project_versions ADD CONSTRAINT fk_project_versions_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)
    """,
    """
ALTER TABLE project_versions ADD CONSTRAINT fk_run_id_build_runs FOREIGN KEY(project_id, run_id) REFERENCES build_runs (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE deployment_records ADD CONSTRAINT fk_deployment_records_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)
    """,
    """
ALTER TABLE deployment_records ADD CONSTRAINT fk_run_id_build_runs FOREIGN KEY(project_id, run_id) REFERENCES build_runs (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
ALTER TABLE deployment_records ADD CONSTRAINT fk_version_id_project_versions FOREIGN KEY(project_id, version_id) REFERENCES project_versions (project_id, id) DEFERRABLE INITIALLY DEFERRED
    """,
    """
CREATE INDEX ix_deployments_version ON deployment_records (version_id)
    """,
    """
ALTER TABLE idempotency_keys ADD CONSTRAINT fk_idempotency_keys_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
    """,
    """
CREATE INDEX ix_idempotency_expiry ON idempotency_keys (expires_at)
    """,
)

INVARIANTS = r"""
CREATE FUNCTION f01_immutable_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'History records are immutable' USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER immutable_brain BEFORE UPDATE OR DELETE ON brain_revisions
FOR EACH ROW EXECUTE FUNCTION f01_immutable_history();
CREATE TRIGGER immutable_requests BEFORE UPDATE OR DELETE ON project_requests
FOR EACH ROW EXECUTE FUNCTION f01_immutable_history();
CREATE TRIGGER immutable_events BEFORE UPDATE OR DELETE ON build_events
FOR EACH ROW EXECUTE FUNCTION f01_immutable_history();
CREATE TRIGGER immutable_versions BEFORE UPDATE OR DELETE ON project_versions
FOR EACH ROW EXECUTE FUNCTION f01_immutable_history();

CREATE FUNCTION f01_guard_run() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE project_archived_at timestamptz;
BEGIN
    -- Same lock order as application services: project, then run.
    SELECT archived_at INTO project_archived_at FROM projects WHERE id = NEW.project_id FOR UPDATE;
    IF NEW.status IN ('queued', 'running') AND project_archived_at IS NOT NULL THEN
        RAISE EXCEPTION 'Archived projects cannot have active runs' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.project_id, NEW.request_id, NEW.input_brain_revision_id, NEW.base_version_id,
            NEW.retry_of_run_id, NEW.attempt, NEW.mode, NEW.scenario_id, NEW.scenario_version)
           IS DISTINCT FROM
           (OLD.project_id, OLD.request_id, OLD.input_brain_revision_id, OLD.base_version_id,
            OLD.retry_of_run_id, OLD.attempt, OLD.mode, OLD.scenario_id, OLD.scenario_version) THEN
            RAISE EXCEPTION 'Run inputs are immutable' USING ERRCODE = '23514';
        END IF;
        IF NEW.status <> OLD.status AND NOT (
            (OLD.status = 'queued' AND NEW.status IN ('running','failed','canceled')) OR
            (OLD.status = 'running' AND NEW.status IN ('succeeded','failed','canceled'))
        ) THEN
            RAISE EXCEPTION 'Invalid run transition' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_run BEFORE INSERT OR UPDATE ON build_runs
FOR EACH ROW EXECUTE FUNCTION f01_guard_run();

CREATE FUNCTION f01_guard_archive() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.archived_at IS NOT NULL AND OLD.archived_at IS NULL AND EXISTS (
        SELECT 1 FROM build_runs WHERE project_id = NEW.id AND status IN ('queued','running')
    ) THEN
        RAISE EXCEPTION 'Active projects cannot be archived' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_archive BEFORE UPDATE OF archived_at ON projects
FOR EACH ROW EXECUTE FUNCTION f01_guard_archive();

CREATE FUNCTION f01_complete_idempotency() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM idempotency_keys WHERE id = NEW.id AND response_status = 0) THEN
        RAISE EXCEPTION 'Idempotency result must commit with the command' USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER complete_idempotency AFTER INSERT OR UPDATE ON idempotency_keys
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION f01_complete_idempotency();
"""


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)
    op.execute(INVARIANTS)


def downgrade() -> None:
    op.execute("DROP TABLE idempotency_keys CASCADE")
    op.execute("DROP TABLE deployment_records CASCADE")
    op.execute("DROP TABLE project_versions CASCADE")
    op.execute("DROP TABLE build_events CASCADE")
    op.execute("DROP TABLE build_runs CASCADE")
    op.execute("DROP TABLE brain_revisions CASCADE")
    op.execute("DROP TABLE project_requests CASCADE")
    op.execute("DROP TABLE projects CASCADE")
    op.execute("DROP TABLE users CASCADE")
    op.execute("DROP FUNCTION f01_complete_idempotency()")
    op.execute("DROP FUNCTION f01_guard_archive()")
    op.execute("DROP FUNCTION f01_guard_run()")
    op.execute("DROP FUNCTION f01_immutable_history()")
