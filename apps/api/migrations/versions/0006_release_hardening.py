"""Retain immutable successful and failed production preparation evidence."""
from alembic import op
revision = '0006_release_hardening'
down_revision = '0005_release_target'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE artifact_preparations ADD COLUMN evidence JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("""CREATE FUNCTION f01_guard_preparation_result() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    IF OLD.state IN ('succeeded','failed','canceled') AND ROW(OLD.state,OLD.artifact_id,OLD.error_code,OLD.evidence) IS DISTINCT FROM ROW(NEW.state,NEW.artifact_id,NEW.error_code,NEW.evidence) THEN
      RAISE EXCEPTION 'Preparation results are immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW; END $$""")
    op.execute('CREATE TRIGGER guard_preparation_result BEFORE UPDATE ON artifact_preparations FOR EACH ROW EXECUTE FUNCTION f01_guard_preparation_result()')


def downgrade() -> None:
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM artifact_preparations WHERE evidence <> '[]'::jsonb) THEN RAISE EXCEPTION 'Production preparation evidence must be retained'; END IF; END $$")
    op.execute('DROP TRIGGER guard_preparation_result ON artifact_preparations')
    op.execute('DROP FUNCTION f01_guard_preparation_result()')
    op.execute('ALTER TABLE artifact_preparations DROP COLUMN evidence')
