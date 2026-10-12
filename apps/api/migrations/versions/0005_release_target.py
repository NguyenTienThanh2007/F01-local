"""Add explicit, durable production target provisioning."""
from alembic import op
revision = '0005_release_target'
down_revision = '0004_phase2c'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("\nCREATE TABLE target_provisioning (\n\tid UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\tauth_session_id UUID, \n\tversion_id UUID NOT NULL, \n\tbrain_revision_id UUID NOT NULL, \n\tprovider_name VARCHAR(100) NOT NULL, \n\tstate VARCHAR(20) NOT NULL, \n\terror_code VARCHAR(100), \n\tepoch INTEGER NOT NULL, \n\tattempts INTEGER NOT NULL, \n\tlease_token UUID, \n\tlease_until TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdeadline_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tCONSTRAINT pk_target_provisioning PRIMARY KEY (id), \n\tCONSTRAINT uq_target_provisioning_project_id UNIQUE (project_id), \n\tCONSTRAINT uq_target_provisioning_provider_name UNIQUE (provider_name), \n\tCONSTRAINT fk_target_provisioning_owner FOREIGN KEY(project_id, user_id) REFERENCES projects (id, owner_user_id), \n\tCONSTRAINT ck_target_provisioning_state CHECK (state IN ('queued','creating','reconciling','ready','failed') AND epoch >= 0 AND attempts >= 0), \n\tCONSTRAINT fk_target_provisioning_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id), \n\tCONSTRAINT fk_target_provisioning_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), \n\tCONSTRAINT fk_target_provisioning_auth_session_id_auth_sessions FOREIGN KEY(auth_session_id) REFERENCES auth_sessions (id)\n)\n\n")
    op.execute('ALTER TABLE target_provisioning ADD CONSTRAINT fk_brain_revision_id_brain_revisions FOREIGN KEY(project_id, brain_revision_id) REFERENCES brain_revisions (project_id, id) DEFERRABLE INITIALLY DEFERRED')
    op.execute('ALTER TABLE target_provisioning ADD CONSTRAINT fk_version_id_project_versions FOREIGN KEY(project_id, version_id) REFERENCES project_versions (project_id, id) DEFERRABLE INITIALLY DEFERRED')

def downgrade() -> None:
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM target_provisioning) THEN RAISE EXCEPTION 'Target provisioning history must be retained'; END IF; END $$")
    op.execute('DROP TABLE target_provisioning')
