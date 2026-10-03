"""Frozen additive Phase 2B execution persistence."""
from alembic import op

revision = "0003_phase2b"
down_revision = "0002_phase2a"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("\nCREATE TABLE execution_jobs (\n\tid UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\trun_id UUID NOT NULL, \n\tplan_id UUID NOT NULL, \n\tauth_session_id UUID, \n\tstate VARCHAR(20) NOT NULL, \n\tphase VARCHAR(40) NOT NULL, \n\tcontext JSONB NOT NULL, \n\tbases JSONB NOT NULL, \n\tepoch INTEGER NOT NULL, \n\tlease_token UUID, \n\tlease_until TIMESTAMP WITH TIME ZONE, \n\tcancel_requested BOOLEAN NOT NULL, \n\trepairs INTEGER NOT NULL, \n\treserved_tokens INTEGER NOT NULL, \n\tpreview_id UUID, \n\tpreview_key VARCHAR(100), \n\tcontainer_name VARCHAR(100), \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdeadline_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_execution_jobs PRIMARY KEY (id), \n\tCONSTRAINT uq_execution_jobs_run_id UNIQUE (run_id), \n\tCONSTRAINT uq_execution_jobs_project_id_id UNIQUE (project_id, id), \n\tCONSTRAINT fk_execution_owner FOREIGN KEY(project_id, user_id) REFERENCES projects (id, owner_user_id), \n\tCONSTRAINT ck_execution_jobs_state CHECK (state IN ('queued','leased','done') AND epoch >= 0 AND repairs >= 0 AND reserved_tokens >= 0), \n\tCONSTRAINT fk_execution_jobs_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id), \n\tCONSTRAINT fk_execution_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), \n\tCONSTRAINT fk_execution_jobs_auth_session_id_auth_sessions FOREIGN KEY(auth_session_id) REFERENCES auth_sessions (id)\n)\n\n")
    op.execute('CREATE INDEX ix_execution_queue ON execution_jobs (state, lease_until, created_at)')
    op.execute('\nCREATE TABLE source_candidates (\n\tid UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tjob_id UUID NOT NULL, \n\tattempt INTEGER NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tparent_digest VARCHAR(64), \n\tsource JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_source_candidates PRIMARY KEY (id), \n\tCONSTRAINT uq_source_candidates_project_id_id UNIQUE (project_id, id), \n\tCONSTRAINT uq_source_candidates_job_id_attempt UNIQUE (job_id, attempt), \n\tCONSTRAINT ck_source_candidates_bounds CHECK (attempt >= 0 AND length(digest) = 64 AND octet_length(source::text) <= 1048576), \n\tCONSTRAINT fk_source_candidates_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)\n)\n\n')
    op.execute('\nCREATE TABLE verification_evidence (\n\tid UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tcandidate_id UUID NOT NULL, \n\tphase VARCHAR(40) NOT NULL, \n\tcontent JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_verification_evidence PRIMARY KEY (id), \n\tCONSTRAINT uq_verification_evidence_project_id_id UNIQUE (project_id, id), \n\tCONSTRAINT uq_verification_evidence_candidate_id_phase UNIQUE (candidate_id, phase), \n\tCONSTRAINT ck_verification_evidence_bounds CHECK (octet_length(content::text) <= 8192), \n\tCONSTRAINT fk_verification_evidence_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)\n)\n\n')
    op.execute("\nCREATE TABLE isolated_previews (\n\tid UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tcandidate_id UUID NOT NULL, \n\tversion_id UUID NOT NULL, \n\tcontainer_name VARCHAR(100) NOT NULL, \n\tcapability_hash VARCHAR(64) NOT NULL, \n\tstate VARCHAR(20) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_isolated_previews PRIMARY KEY (id), \n\tCONSTRAINT uq_isolated_previews_project_id_id UNIQUE (project_id, id), \n\tCONSTRAINT uq_isolated_previews_version_id UNIQUE (version_id), \n\tCONSTRAINT uq_isolated_previews_container_name UNIQUE (container_name), \n\tCONSTRAINT ck_isolated_previews_state CHECK (state IN ('ready','expired','cleanup_pending','removed')), \n\tCONSTRAINT fk_isolated_previews_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)\n)\n\n")
    op.execute('ALTER TABLE execution_jobs ADD CONSTRAINT fk_plan_id_planning_proposals FOREIGN KEY(project_id, plan_id) REFERENCES planning_proposals (project_id, id) DEFERRABLE INITIALLY DEFERRED')
    op.execute('ALTER TABLE execution_jobs ADD CONSTRAINT fk_run_id_build_runs FOREIGN KEY(project_id, run_id) REFERENCES build_runs (project_id, id) DEFERRABLE INITIALLY DEFERRED')
    op.execute('ALTER TABLE source_candidates ADD CONSTRAINT fk_job_id_execution_jobs FOREIGN KEY(project_id, job_id) REFERENCES execution_jobs (project_id, id) DEFERRABLE INITIALLY DEFERRED')
    op.execute('ALTER TABLE verification_evidence ADD CONSTRAINT fk_candidate_id_source_candidates FOREIGN KEY(project_id, candidate_id) REFERENCES source_candidates (project_id, id) DEFERRABLE INITIALLY DEFERRED')
    op.execute('ALTER TABLE isolated_previews ADD CONSTRAINT fk_version_id_project_versions FOREIGN KEY(project_id, version_id) REFERENCES project_versions (project_id, id) DEFERRABLE INITIALLY DEFERRED')
    op.execute('ALTER TABLE isolated_previews ADD CONSTRAINT fk_candidate_id_source_candidates FOREIGN KEY(project_id, candidate_id) REFERENCES source_candidates (project_id, id) DEFERRABLE INITIALLY DEFERRED')
    op.execute("ALTER TABLE build_runs DROP CONSTRAINT ck_build_runs_mode")
    op.execute("ALTER TABLE build_runs ADD CONSTRAINT ck_build_runs_mode CHECK (mode IN ('simulated','real'))")
    op.execute("ALTER TABLE build_events DROP CONSTRAINT ck_build_events_mode")
    op.execute("ALTER TABLE build_events ADD CONSTRAINT ck_build_events_mode CHECK (mode IS NULL OR mode IN ('simulated','real'))")
    op.execute("ALTER TABLE project_versions DROP CONSTRAINT ck_project_versions_output")
    op.execute("ALTER TABLE project_versions ADD CONSTRAINT ck_project_versions_output CHECK (number > 0 AND mode IN ('simulated','real') AND jsonb_typeof(preview_descriptor) = 'object')")
    op.execute('CREATE TRIGGER immutable_source_candidates BEFORE UPDATE OR DELETE ON source_candidates FOR EACH ROW EXECUTE FUNCTION f01_immutable_history()')
    op.execute('CREATE TRIGGER immutable_verification_evidence BEFORE UPDATE OR DELETE ON verification_evidence FOR EACH ROW EXECUTE FUNCTION f01_immutable_history()')

def downgrade() -> None:
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM build_runs WHERE mode = 'real') THEN RAISE EXCEPTION 'Phase 2B history must be retained before downgrade'; END IF; END $$")
    op.execute('DROP TABLE isolated_previews CASCADE')
    op.execute('DROP TABLE verification_evidence CASCADE')
    op.execute('DROP TABLE source_candidates CASCADE')
    op.execute('DROP TABLE execution_jobs CASCADE')
    op.execute("ALTER TABLE build_runs DROP CONSTRAINT ck_build_runs_mode")
    op.execute("ALTER TABLE build_runs ADD CONSTRAINT ck_build_runs_mode CHECK (mode = 'simulated')")
    op.execute("ALTER TABLE build_events DROP CONSTRAINT ck_build_events_mode")
    op.execute("ALTER TABLE build_events ADD CONSTRAINT ck_build_events_mode CHECK (mode IS NULL OR mode = 'simulated')")
    op.execute("ALTER TABLE project_versions DROP CONSTRAINT ck_project_versions_output")
    op.execute("ALTER TABLE project_versions ADD CONSTRAINT ck_project_versions_output CHECK (number > 0 AND mode = 'simulated' AND jsonb_typeof(preview_descriptor) = 'object')")
