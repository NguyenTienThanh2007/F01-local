"""Controlled release persistence/fault tests. These are not live provider acceptance."""
import asyncio
import base64
import hashlib
import json
from datetime import timedelta
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from f01.application import releases as service, execution
from f01.application.execution import now
from f01.application.projects import workspace, resolve_principal
from f01.config import Settings
from f01.db import models as db
from f01.db.session import Database
from f01.domain.errors import ApplicationError
from f01.domain.planning import ProjectPlan
from f01.domain.releases import PrepareRelease, PromoteRelease
from f01.execution.worker import BuildWorker
from f01.release.package import validate_package, package_digest, OUTPUT_CONFIG
from f01.release.provider import StagedDeployment, ReleaseProviderError
from f01.release.worker import ReleaseWorker
from tests.persistence.test_phase2b import setup_build, SourceProvider, ControlledSandbox


@pytest.fixture
def release_settings(project_settings: Settings) -> Settings:
    return project_settings.model_copy(update={'real_execution_enabled': True, 'execution_mode': 'real', 'release_enabled': True, 'sandbox_image_id': 'sha256:'+'a'*64, 'planning_daily_token_budget': 10000000})


def package(marker: dict[str, object]) -> dict[str, object]:
    values = {'config.json': json.dumps(OUTPUT_CONFIG), 'static/index.html': '<main>Verified dashboard</main>', 'static/__f01_release.json': json.dumps(marker)}
    return {'files': [{'path': '.vercel/output/'+path, 'data': base64.b64encode(content.encode()).decode(), 'sha256': hashlib.sha256(content.encode()).hexdigest()} for path, content in values.items()]}


def setup(database: Database, settings: Settings, plan: ProjectPlan) -> tuple[UUID, UUID, PromoteRelease]:
    owner, pid, body = setup_build(database, settings, plan)
    execution.queue(database, settings, owner, pid, body, 'build')
    asyncio.run(BuildWorker(database, settings, ControlledSandbox(), SourceProvider()).run_once())
    config = service.configure(database, pid, 'prj_'+pid.hex, None, 'https://f01-'+pid.hex+'.vercel.app', settings.factory_origin)
    saved = workspace(database, owner, pid)
    assert saved.current_version
    preparation = service.prepare(database, settings, owner, pid, PrepareRelease(version_id=saved.current_version.id, configuration_id=config, expected_brain_revision_id=saved.project.current_brain_revision_id), 'prepare')
    with database.session() as session, session.begin():
        _, candidate, _, _ = service.source_for_version(session, pid, saved.current_version.id)
        content = package({'preparation_id': str(preparation.id), 'source_digest': candidate.digest})
        artifact = db.ReleaseArtifact(id=uuid4(), project_id=pid, preparation_id=preparation.id, version_id=saved.current_version.id, brain_revision_id=saved.project.current_brain_revision_id,
            configuration_id=config, candidate_id=candidate.id, digest=package_digest(validate_package(content)), package=content, manifest={'test': 'controlled packaging only'}, created_at=now())
        session.add(artifact)
        row = session.get(db.ArtifactPreparation, preparation.id)
        assert row
        row.artifact_id, row.state = artifact.id, 'succeeded'
        artifact_id = artifact.id
    return owner, pid, PromoteRelease(artifact_id=artifact_id, configuration_id=config, expected_version_id=saved.current_version.id,
        expected_brain_revision_id=saved.project.current_brain_revision_id, expected_production_release_id=None, expected_target_generation=0)


class ControlledProvider:
    def __init__(self) -> None:
        self.current: str | None = None
        self.staged: dict[str, StagedDeployment] = {}
        self.stage_calls = self.promote_calls = self.cancel_calls = 0
        self.lose_stage = self.lose_promote = self.bad_public = self.unknown_stage = False

    async def upload(self, config: db.ReleaseConfiguration, artifact: db.ReleaseArtifact) -> None:
        validate_package(artifact.package, artifact.digest)

    async def stage(self, config: db.ReleaseConfiguration, artifact: db.ReleaseArtifact, operation: str) -> StagedDeployment:
        self.stage_calls += 1
        value = StagedDeployment('dpl_'+str(self.stage_calls), 'https://staged.vercel.app', 'READY')
        self.staged[operation] = value
        if self.lose_stage:
            raise ReleaseProviderError('RELEASE_PROVIDER_UNAVAILABLE', uncertain=True)
        return value

    async def find(self, config: db.ReleaseConfiguration, artifact: db.ReleaseArtifact, operation: str) -> StagedDeployment | None:
        return None if self.unknown_stage else self.staged.get(operation)

    async def observe(self, config: db.ReleaseConfiguration, artifact: db.ReleaseArtifact, operation: str, deployment: str) -> StagedDeployment:
        return self.staged[operation]

    async def routing(self, config: db.ReleaseConfiguration) -> str | None:
        return self.current

    async def promote(self, config: db.ReleaseConfiguration, deployment: str) -> None:
        self.promote_calls += 1
        self.current = deployment
        if self.lose_promote:
            raise ReleaseProviderError('RELEASE_PROVIDER_UNAVAILABLE', uncertain=True)

    async def cancel(self, config: db.ReleaseConfiguration, deployment: str) -> None:
        self.cancel_calls += 1

    async def clear(self, config: db.ReleaseConfiguration, deployment: str) -> None:
        assert self.current == deployment
        self.current = None

    async def health(self, url: str, artifact: db.ReleaseArtifact) -> None:
        if self.bad_public and 'staged' not in url:
            raise ReleaseProviderError('RELEASE_HEALTH_FAILED')


def tick(database: Database, settings: Settings, provider: ControlledProvider, count: int = 1) -> None:
    for _ in range(count):
        with database.session() as session, session.begin():
            for row in session.scalars(select(db.ReleaseOperation).where(db.ReleaseOperation.state.not_in(service.TERMINAL))):
                row.next_attempt_at = now()-timedelta(seconds=1)
        asyncio.run(ReleaseWorker(database, settings, provider).run_once())


def test_release_success_idempotency_independent_preview_and_immutable_history(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    before = workspace(database, owner, pid)
    release = service.promote(database, release_settings, owner, pid, command, 'deploy', None)
    assert service.promote(database, release_settings, owner, pid, command, 'deploy', None).id == release.id
    assert service.promote(database, release_settings, owner, pid, command, 'another-key', None).id == release.id
    provider = ControlledProvider()
    tick(database, release_settings, provider, 8)
    state = service.workspace(database, release_settings, owner, pid)
    assert state.current_release_id == release.id and state.target_generation == 1
    assert state.releases[0].state == 'succeeded' and provider.stage_calls == provider.promote_calls == 1
    after = workspace(database, owner, pid)
    assert after.current_brain == before.current_brain and after.current_version == before.current_version and after.preview == before.preview
    for table in ('release_artifacts', 'release_intents', 'release_configurations', 'release_observations'):
        with database.session() as session, pytest.raises(DBAPIError):
            session.execute(text('DELETE FROM '+table))
    with database.session() as session, pytest.raises(DBAPIError):
        session.execute(text("UPDATE release_operations SET state='queued'"))


@pytest.mark.parametrize('loss', ['stage', 'promote'])
def test_response_loss_reconciles_without_second_write(database: Database, release_settings: Settings, project_plan: ProjectPlan, loss: str) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    service.promote(database, release_settings, owner, pid, command, 'deploy', None)
    provider = ControlledProvider()
    provider.lose_stage, provider.lose_promote = loss == 'stage', loss == 'promote'
    tick(database, release_settings, provider, 10)
    assert service.workspace(database, release_settings, owner, pid).releases[0].state == 'succeeded'
    assert provider.stage_calls == provider.promote_calls == 1


def test_unknown_stage_blocks_new_release_and_never_blindly_repeats(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    service.promote(database, release_settings, owner, pid, command, 'deploy', None)
    provider = ControlledProvider()
    provider.lose_stage = provider.unknown_stage = True
    tick(database, release_settings, provider, 12)
    state = service.workspace(database, release_settings, owner, pid)
    assert state.releases[0].state == 'reconciling' and state.current_release_id is None
    assert provider.stage_calls == 1 and provider.promote_calls == 0
    with database.session() as session, pytest.raises(ApplicationError, match='RELEASE_IN_PROGRESS'):
        service.guard(session, pid)


def test_first_release_failed_public_health_clears_only_its_alias(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    before = workspace(database, owner, pid)
    service.promote(database, release_settings, owner, pid, command, 'deploy', None)
    provider = ControlledProvider()
    provider.bad_public = True
    tick(database, release_settings, provider, 10)
    state = service.workspace(database, release_settings, owner, pid)
    assert state.current_release_id is None and state.target_generation == 0 and state.releases[0].state == 'failed'
    assert provider.current is None and workspace(database, owner, pid).preview == before.preview


def test_cancellation_before_dispatch_and_foreign_owner_denial(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    foreign = resolve_principal(database, 'release-foreign').id
    with pytest.raises(ApplicationError, match='NOT_FOUND'):
        service.workspace(database, release_settings, foreign, pid)
    release = service.promote(database, release_settings, owner, pid, command, 'deploy', None)
    with pytest.raises(ApplicationError, match='NOT_FOUND'):
        service.cancel(database, foreign, pid, release.id)
    assert service.cancel(database, owner, pid, release.id).state == 'canceled'
    provider = ControlledProvider()
    tick(database, release_settings, provider, 2)
    assert provider.stage_calls == provider.promote_calls == 0


def test_stale_generation_and_reused_key_fail_closed(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    with pytest.raises(ApplicationError, match='RELEASE_STALE_CONTEXT'):
        service.promote(database, release_settings, owner, pid, command.model_copy(update={'expected_target_generation': 1}), 'stale', None)
    service.promote(database, release_settings, owner, pid, command, 'deploy', None)
    with pytest.raises(ApplicationError, match='IDEMPOTENCY_KEY_REUSED'):
        service.promote(database, release_settings, owner, pid, command.model_copy(update={'expected_target_generation': 1}), 'deploy', None)


def test_revoked_identity_before_promotion_never_cuts_over(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    settings = release_settings.model_copy(update={'auth_mode': 'oidc'})
    service.promote(database, settings, owner, pid, command, 'deploy', None)
    provider = ControlledProvider()
    tick(database, settings, provider, 2)
    assert service.workspace(database, settings, owner, pid).releases[0].state == 'failed'
    assert provider.stage_calls == provider.promote_calls == 0


def test_modified_version_requires_new_package_and_failed_redeploy_retains_live(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    from f01.application.projects import record_change
    from f01.domain.projects import RecordChange
    from tests.persistence.test_phase2b import review_plan
    owner, pid, first = setup(database, release_settings, project_plan)
    provider = ControlledProvider()
    release = service.promote(database, release_settings, owner, pid, first, 'first-live', None)
    tick(database, release_settings, provider, 8)
    before = workspace(database, owner, pid)
    change = record_change(database, owner, pid, RecordChange(text='Add a priority filter to the existing leads overview.', base_brain_revision_id=before.project.current_brain_revision_id, base_version_id=before.project.current_version_id), 'modify')
    command = review_plan(database, release_settings, project_plan, owner, pid, change.id, 'change')
    execution.queue(database, release_settings, owner, pid, command, 'rebuild')
    asyncio.run(BuildWorker(database, release_settings, ControlledSandbox(), SourceProvider()).run_once())
    after = workspace(database, owner, pid)
    assert after.current_version and before.current_version and after.current_version.id != before.current_version.id
    assert service.workspace(database, release_settings, owner, pid).current_release_id == release.id
    prepared = service.prepare(database, release_settings, owner, pid, PrepareRelease(version_id=after.current_version.id, configuration_id=first.configuration_id, expected_brain_revision_id=after.project.current_brain_revision_id), 'new-package')
    with database.session() as session, session.begin():
        _, candidate, _, _ = service.source_for_version(session, pid, after.current_version.id)
        content = package({'test': 'v2-controlled'})
        saved = db.ReleaseArtifact(id=uuid4(), project_id=pid, preparation_id=prepared.id, version_id=after.current_version.id, brain_revision_id=after.project.current_brain_revision_id,
            configuration_id=first.configuration_id, candidate_id=candidate.id, digest=package_digest(validate_package(content)), package=content, manifest={'test': 'controlled-v2'}, created_at=now())
        session.add(saved)
        row = session.get(db.ArtifactPreparation, prepared.id)
        assert row
        row.state, row.artifact_id = 'succeeded', saved.id
        artifact_id = saved.id
    second = PromoteRelease(artifact_id=artifact_id, configuration_id=first.configuration_id, expected_brain_revision_id=after.project.current_brain_revision_id,
        expected_version_id=after.current_version.id, expected_production_release_id=release.id, expected_target_generation=1)
    service.promote(database, release_settings, owner, pid, second, 'redeploy', None)
    original_health = provider.health
    async def fail_updated_public(url: str, artifact: db.ReleaseArtifact) -> None:
        if artifact.id == artifact_id and 'staged' not in url:
            raise ReleaseProviderError('RELEASE_HEALTH_FAILED')
        await original_health(url, artifact)
    provider.health = fail_updated_public  # type: ignore[method-assign]
    tick(database, release_settings, provider, 12)
    final = service.workspace(database, release_settings, owner, pid)
    assert final.current_release_id == release.id and final.target_generation == 1
    assert final.releases[0].state == 'failed' and final.releases[1].state == 'succeeded'
    assert provider.current == 'dpl_1' and provider.stage_calls == 2 and provider.promote_calls == 3
    assert workspace(database, owner, pid).preview == after.preview
    with database.session() as session:
        first_source = session.get(db.SourceCandidate, service.source_for_version(session, pid, before.current_version.id)[1].id)
        next_source = service.source_for_version(session, pid, after.current_version.id)[1]
        assert first_source and next_source.parent_digest == first_source.digest
        source_one, source_two = first_source.source['files'], next_source.source['files']
        assert isinstance(source_one, list) and isinstance(source_two, list)
        assert next(f for f in source_one if f['path'] == 'app/layout.tsx') == next(f for f in source_two if f['path'] == 'app/layout.tsx')


@pytest.mark.parametrize('race', ['cancel', 'deadline'])
def test_cancel_or_deadline_during_public_health_compensates_before_committing(database: Database, release_settings: Settings, project_plan: ProjectPlan, race: str) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    release = service.promote(database, release_settings, owner, pid, command, 'race', None)
    provider = ControlledProvider()
    original = provider.health
    async def mutate_during_health(url: str, artifact: db.ReleaseArtifact) -> None:
        await original(url, artifact)
        if 'staged' not in url:
            if race == 'cancel':
                service.cancel(database, owner, pid, release.id)
            else:
                with database.session() as session, session.begin():
                    # Simulate time crossing the frozen deadline during an in-flight health observation.
                    session.execute(text('ALTER TABLE release_operations DISABLE TRIGGER guard_release_operation'))
                    row = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.release_id == release.id))
                    assert row
                    row.deadline_at = now()-timedelta(seconds=1)
                    session.flush()
                    session.execute(text('ALTER TABLE release_operations ENABLE TRIGGER guard_release_operation'))
    provider.health = mutate_during_health  # type: ignore[method-assign]
    tick(database, release_settings, provider, 12)
    final = service.workspace(database, release_settings, owner, pid)
    assert final.current_release_id is None and final.target_generation == 0
    assert final.releases[0].state == ('canceled' if race == 'cancel' else 'failed')
    assert provider.current is None


def test_real_mode_creation_retains_intent_when_runtime_is_unavailable(project_settings: Settings) -> None:
    from fastapi.testclient import TestClient
    from f01.main import create_app
    settings = project_settings.model_copy(update={'execution_mode': 'real', 'real_execution_enabled': False, 'simulation_runner_enabled': False})
    with TestClient(create_app(settings)) as client:
        client.headers['Authorization'] = 'Bearer '+settings.dev_api_token.get_secret_value()
        response = client.post('/v1/projects', json={'title': 'Real intent', 'brief': 'Build a browser dashboard for property leads.'}, headers={'Idempotency-Key': 'runtime-unavailable'})
        assert response.status_code == 201 and response.json()['execution_mode'] == 'real' and response.json()['run_id'] is None
        saved = client.get(response.headers['Location']+'/workspace').json()
        assert saved['active_run'] is None and saved['current_version'] is None


def test_failed_release_retry_has_new_immutable_history_and_idempotent_intent(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    first = service.promote(database, release_settings, owner, pid, command, 'first', None)
    provider = ControlledProvider()
    provider.bad_public = True
    tick(database, release_settings, provider, 10)
    assert service.workspace(database, release_settings, owner, pid).releases[0].state == 'failed'
    second = service.promote(database, release_settings, owner, pid, command, 'retry', None, first.id)
    assert second.id != first.id and service.promote(database, release_settings, owner, pid, command, 'retry', None, first.id).id == second.id
    provider.bad_public = False
    tick(database, release_settings, provider, 10)
    saved = service.workspace(database, release_settings, owner, pid)
    assert saved.current_release_id == second.id and saved.target_generation == 1 and saved.releases[1].state == 'failed'


def test_observation_resume_keeps_pending_write_identity(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    release = service.promote(database, release_settings, owner, pid, command, 'uncertain', None)
    provider = ControlledProvider()
    provider.lose_stage = provider.unknown_stage = True
    tick(database, release_settings, provider, 4)
    with database.session() as session, session.begin():
        op = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.release_id == release.id))
        assert op
        op.attempts = 120
    service.resume(database, owner, pid, release.id)
    provider.unknown_stage = False
    tick(database, release_settings, provider, 10)
    saved = service.workspace(database, release_settings, owner, pid)
    assert saved.current_release_id == release.id and provider.stage_calls == 1 and provider.promote_calls == 1


def test_definitive_provider_auth_rejection_can_be_explicitly_retried(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    release = service.promote(database, release_settings, owner, pid, command, 'auth-reject', None)
    provider = ControlledProvider()
    original = provider.stage
    async def unauthorized(config: db.ReleaseConfiguration, artifact: db.ReleaseArtifact, operation: str) -> StagedDeployment:
        raise ReleaseProviderError('RELEASE_PROVIDER_AUTHENTICATION')
    provider.stage = unauthorized  # type: ignore[method-assign]
    tick(database, release_settings, provider, 4)
    assert service.workspace(database, release_settings, owner, pid).releases[0].state == 'failed'
    retried = service.promote(database, release_settings, owner, pid, command, 'auth-reviewed-retry', None, release.id)
    provider.stage = original  # type: ignore[method-assign]
    tick(database, release_settings, provider, 10)
    assert service.workspace(database, release_settings, owner, pid).current_release_id == retried.id


def test_release_and_packaging_lease_capacity_is_global(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    owner, pid, command = setup(database, release_settings, project_plan)
    other_owner, other_pid, other_command = setup(database, release_settings, project_plan)
    service.promote(database, release_settings, owner, pid, command, 'capacity-one', None)
    service.promote(database, release_settings, other_owner, other_pid, other_command, 'capacity-two', None)
    worker = ReleaseWorker(database, release_settings, ControlledProvider())
    assert worker.claim() is not None
    assert worker.claim() is None


def test_release_publication_locks_project_before_operation(database: Database, release_settings: Settings, project_plan: ProjectPlan) -> None:
    from concurrent.futures import ThreadPoolExecutor
    import time
    owner, pid, command = setup(database, release_settings, project_plan)
    service.promote(database, release_settings, owner, pid, command, 'lock-order', None)
    worker = ReleaseWorker(database, release_settings, ControlledProvider())
    claim = worker.claim()
    assert claim
    identifier, token = claim
    with ThreadPoolExecutor(max_workers=1) as pool:
        with database.session() as session, session.begin():
            session.get(db.Project, pid, with_for_update=True)
            future = pool.submit(worker.save, identifier, token, state='failed', error='CONTROLLED_TEST', finish=True)
            for _ in range(200):
                session.execute(text('SELECT pg_stat_clear_snapshot()'))
                blocked = session.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query LIKE '%projects%FOR UPDATE%'"))
                if blocked:
                    break
                time.sleep(.01)
            else:
                raise AssertionError('The worker did not reach the project-lock barrier.')
            # Cancellation/settings already own the project lock. The operation must still be available.
            operation = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.id == identifier).with_for_update(nowait=True))
            assert operation and operation.state == 'queued'
        future.result(timeout=5)
