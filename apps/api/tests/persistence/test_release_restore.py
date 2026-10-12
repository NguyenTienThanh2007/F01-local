"""Actual PostgreSQL dump/restore of populated source and production history."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from uuid import uuid4
import psycopg
from sqlalchemy.engine import make_url
from sqlalchemy import select, text
from f01.application import releases
from f01.config import Settings
from f01.db import models as db
from f01.db.session import Database
from f01.domain.planning import ProjectPlan
from tests.persistence.test_releases import setup, tick, ControlledProvider
import pytest


@pytest.fixture
def release_settings(project_settings: Settings) -> Settings:
    return project_settings.model_copy(update={'real_execution_enabled': True, 'execution_mode': 'real', 'release_enabled': True, 'sandbox_image_id': 'sha256:'+'a'*64, 'planning_daily_token_budget': 10000000})


def test_populated_release_metadata_and_durable_bytes_restore(database: Database, database_url: str, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    release = releases.promote(database, release_settings, owner, pid, command, 'backup-release', None)
    tick(database, release_settings, ControlledProvider(), 8)
    before = releases.workspace(database, release_settings, owner, pid)
    parsed = make_url(database_url)
    assert (parsed.database or '').startswith('f01_test_')
    bin_dir = Path(os.environ.get('F01_TEST_PG_BIN') or (str(Path(found).parent) if (found := shutil.which('pg_dump')) else '/Library/PostgreSQL/18/bin'))
    env = {**os.environ, 'PGHOST': str(parsed.host), 'PGPORT': str(parsed.port or 5432), 'PGUSER': str(parsed.username), 'PGPASSWORD': parsed.password or ''}
    restore_name = 'f01_test_restore_'+uuid4().hex
    with psycopg.connect(host=parsed.host, port=parsed.port, user=parsed.username, password=parsed.password, dbname='postgres', autocommit=True) as control:
        control.execute('CREATE DATABASE '+restore_name)
        try:
            with tempfile.TemporaryDirectory(prefix='f01-release-restore-') as temporary:
                dump = Path(temporary)/'metadata.dump'
                subprocess.run([str(bin_dir/'pg_dump'), '--format=custom', '--file='+str(dump), str(parsed.database)], env=env, check=True, capture_output=True)
                subprocess.run([str(bin_dir/'pg_restore'), '--no-owner', '--no-privileges', '--exit-on-error', '--dbname='+restore_name, str(dump)], env=env, check=True, capture_output=True)
                restored = Database(parsed.set(database=restore_name).render_as_string(hide_password=False))
                try:
                    after = releases.workspace(restored, release_settings, owner, pid)
                    assert after == before and after.current_release_id == release.id
                    with restored.session() as session:
                        assert session.scalar(select(db.SourceCandidate.digest)) is not None
                        artifact = session.get(db.ReleaseArtifact, command.artifact_id)
                        assert artifact
                        from f01.release.package import validate_package
                        assert validate_package(artifact.package, artifact.digest)
                        assert session.scalar(text('SELECT version_num FROM alembic_version')) == '0006_release_hardening'
                finally:
                    restored.close()
        finally:
            control.execute('DROP DATABASE '+restore_name)
