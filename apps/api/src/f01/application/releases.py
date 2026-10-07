"""Owned, digest-bound production commands. Generated code never executes here."""
from collections.abc import Mapping
import json
import re
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from f01.application.execution import now
from f01.application.identity import digest
from f01.application.planning import lock_owner
from f01.application.projects import owned_project, append_event
from f01.application.runs import available
from f01.config import Settings
from f01.db import models as db
from f01.db.session import Database
from f01.domain import releases as dto
from f01.domain.errors import ApplicationError
from f01.domain.execution import CommandEvidence
from f01.domain.source import SourceArtifact
from f01.application.source_artifacts import validate_artifact

TERMINAL = ('succeeded', 'failed', 'canceled')


def fingerprint(value: Mapping[str, object]) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')))


def public_url(value: str, factory_origin: str = '') -> str:
    parsed = urlsplit(value)
    factory = urlsplit(factory_origin).hostname
    if (parsed.scheme != 'https' or not parsed.hostname or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}\.vercel\.app', parsed.hostname)
        or parsed.netloc != parsed.hostname or parsed.path not in ('', '/') or parsed.query or parsed.fragment
        or factory and (factory == parsed.hostname or factory.endswith('.vercel.app'))):
        raise ApplicationError('RELEASE_URL_INVALID')
    return 'https://' + parsed.hostname


def active(session: Session, project_id: UUID) -> bool:
    return session.scalar(select(db.ReleaseOperation.id).where(db.ReleaseOperation.project_id == project_id, db.ReleaseOperation.state.not_in(TERMINAL)).limit(1)) is not None


def guard(session: Session, project_id: UUID) -> None:
    if active(session, project_id):
        raise ApplicationError('RELEASE_IN_PROGRESS')


def configured(session: Session, project_id: UUID, config_id: UUID | None = None) -> tuple[db.ProductionTarget, db.ReleaseConfiguration]:
    target = session.scalar(select(db.ProductionTarget).where(db.ProductionTarget.project_id == project_id))
    if target is None:
        raise ApplicationError('RELEASE_NOT_CONFIGURED')
    config = session.get(db.ReleaseConfiguration, target.configuration_id)
    assert config is not None
    if config_id is not None and config.id != config_id:
        raise ApplicationError('RELEASE_STALE_CONTEXT')
    return target, config


def configure(database: Database, project_id: UUID, provider_project: str, team: str | None, url: str, factory_origin: str) -> UUID:
    """Operator-only binding. API callers cannot choose provider resources or URLs."""
    url = public_url(url, factory_origin)
    if not re.fullmatch(r'prj_[A-Za-z0-9]{1,90}', provider_project) or team and not re.fullmatch(r'team_[A-Za-z0-9]{1,90}', team):
        raise ApplicationError('VALIDATION_ERROR')
    content = {'project_id': str(project_id), 'provider_project_id': provider_project, 'team_id': team, 'public_url': url, 'profile': 'next-static-v1'}
    with database.session() as session, session.begin():
        project = session.get(db.Project, project_id, with_for_update=True)
        if project is None:
            raise ApplicationError('NOT_FOUND')
        target = session.scalar(select(db.ProductionTarget).where(db.ProductionTarget.project_id == project_id))
        if target:
            _, config = configured(session, project_id)
            if config.digest == fingerprint(content):
                return config.id
            raise ApplicationError('RELEASE_CONFIGURATION_LOCKED')
        identifier = uuid4()
        session.add(db.ReleaseConfiguration(id=identifier, project_id=project_id, provider='vercel', profile='next-static-v1', provider_project_id=provider_project,
            provider_team_id=team, public_url=url, digest=fingerprint(content), created_at=now()))
        session.add(db.ProductionTarget(id=uuid4(), project_id=project_id, configuration_id=identifier, current_release_id=None, generation=0))
        return identifier


def receipt(session: Session, owner: UUID, project_id: UUID, key: str, command: str, body: dict[str, object]) -> tuple[db.IdempotencyKey, UUID | None]:
    scope = f'/v1/projects/{project_id}/{command}'
    saved = session.scalar(select(db.IdempotencyKey).where(db.IdempotencyKey.user_id == owner, db.IdempotencyKey.route_scope == scope, db.IdempotencyKey.method == 'POST', db.IdempotencyKey.key == key))
    hashed = fingerprint(body)
    if saved:
        if saved.request_hash != hashed:
            raise ApplicationError('IDEMPOTENCY_KEY_REUSED')
        return saved, UUID(str(saved.response_body['id']))
    row = db.IdempotencyKey(id=uuid4(), user_id=owner, method='POST', route_scope=scope, key=key, request_hash=hashed, response_status=202,
        response_body={}, created_at=now(), expires_at=now() + timedelta(days=1))
    session.add(row)
    return row, None


def source_for_version(session: Session, project_id: UUID, version_id: UUID) -> tuple[db.ProjectVersion, db.SourceCandidate, SourceArtifact, list[db.VerificationEvidence]]:
    version = session.get(db.ProjectVersion, version_id)
    preview = session.scalar(select(db.IsolatedPreview).where(db.IsolatedPreview.project_id == project_id, db.IsolatedPreview.version_id == version_id))
    if not version or version.project_id != project_id or version.mode != 'real' or not preview:
        raise ApplicationError('RELEASE_VERIFICATION_REQUIRED')
    candidate = session.get(db.SourceCandidate, preview.candidate_id)
    assert candidate is not None
    source = SourceArtifact.model_validate_json(json.dumps(candidate.source))
    validate_artifact(source)
    job = session.get(db.ExecutionJob, candidate.job_id)
    run = session.get(db.BuildRun, version.run_id)
    if (candidate.project_id != project_id or candidate.digest != source.digest or source.lineage.project_id != project_id or not job or not run
        or job.run_id != run.id or job.plan_id != source.lineage.plan_id or run.status != 'succeeded' or run.request_id != source.lineage.request_id
        or run.input_brain_revision_id != source.lineage.brain_revision_id or run.base_version_id != source.lineage.version_id):
        raise ApplicationError('RELEASE_VERIFICATION_REQUIRED')
    evidence = list(session.scalars(select(db.VerificationEvidence).where(db.VerificationEvidence.candidate_id == candidate.id)))
    checked = {row.phase: CommandEvidence.model_validate(row.content) for row in evidence}
    if set(checked) != {'materialization', 'install', 'typecheck', 'build', 'test', 'verification'} or any(x.exit_code != 0 for x in checked.values()) or len({x.image_id for x in checked.values()}) != 1:
        raise ApplicationError('RELEASE_VERIFICATION_REQUIRED')
    return version, candidate, source, evidence


def preparation(row: db.ArtifactPreparation) -> dto.ArtifactPreparation:
    return dto.ArtifactPreparation.model_validate(row)


def detail(session: Session, row: db.ReleaseIntent) -> dto.ReleaseDetail:
    op = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.release_id == row.id))
    assert op is not None
    return dto.ReleaseDetail(id=row.id, project_id=row.project_id, artifact_id=row.artifact_id, configuration_id=row.configuration_id, version_id=row.version_id,
        previous_release_id=row.previous_release_id, state=op.state, public_url=op.public_url, deployment_url=op.deployment_url, error_code=op.error_code,
        cancel_requested=op.cancel_requested, last_observed_at=op.last_observed_at, created_at=row.created_at)


def prepare(database: Database, settings: Settings, owner: UUID, project_id: UUID, body: dto.PrepareRelease, key: str) -> dto.ArtifactPreparation:
    with database.session() as session, session.begin():
        lock_owner(session, owner)
        project = owned_project(session, owner, project_id, lock=True)
        if not settings.release_enabled:
            raise ApplicationError('RELEASE_UNAVAILABLE')
        saved, replay = receipt(session, owner, project_id, key, 'release-artifacts', body.model_dump(mode='json'))
        if replay:
            row = session.get(db.ArtifactPreparation, replay)
            assert row is not None
            return preparation(row)
        intent = fingerprint(body.model_dump(mode='json'))
        row = session.scalar(select(db.ArtifactPreparation).where(db.ArtifactPreparation.project_id == project_id, db.ArtifactPreparation.intent_hash == intent))
        if row is None:
            configured(session, project_id, body.configuration_id)
            available(session, project, body.expected_brain_revision_id, body.version_id)
            guard(session, project_id)
            version, _, _, _ = source_for_version(session, project_id, body.version_id)
            if version.brain_revision_id != body.expected_brain_revision_id:
                raise ApplicationError('RELEASE_STALE_CONTEXT')
            row = db.ArtifactPreparation(id=uuid4(), project_id=project_id, version_id=body.version_id, brain_revision_id=body.expected_brain_revision_id,
                configuration_id=body.configuration_id, intent_hash=intent, state='queued', epoch=0, created_at=now(), deadline_at=now()+timedelta(seconds=settings.release_timeout_seconds))
            session.add(row)
            session.flush()
            append_event(session, project, type='release.packaging_queued', message='Production package preparation saved.', actor=owner)
        saved.response_body = {'id': str(row.id)}
        return preparation(row)


def promote(database: Database, settings: Settings, owner: UUID, project_id: UUID, body: dto.PromoteRelease, key: str, auth_id: UUID | None) -> dto.ReleaseDetail:
    with database.session() as session, session.begin():
        lock_owner(session, owner)
        project = owned_project(session, owner, project_id, lock=True)
        if not settings.release_enabled:
            raise ApplicationError('RELEASE_UNAVAILABLE')
        saved, replay = receipt(session, owner, project_id, key, 'releases', body.model_dump(mode='json'))
        if replay:
            row = session.get(db.ReleaseIntent, replay)
            assert row is not None
            return detail(session, row)
        intent = fingerprint(body.model_dump(mode='json'))
        row = session.scalar(select(db.ReleaseIntent).where(db.ReleaseIntent.project_id == project_id, db.ReleaseIntent.intent_hash == intent))
        if row is None:
            target, config = configured(session, project_id, body.configuration_id)
            available(session, project, body.expected_brain_revision_id, body.expected_version_id)
            guard(session, project_id)
            artifact = session.get(db.ReleaseArtifact, body.artifact_id)
            if not artifact or artifact.project_id != project_id:
                raise ApplicationError('NOT_FOUND')
            if (artifact.version_id != body.expected_version_id or artifact.brain_revision_id != body.expected_brain_revision_id or artifact.configuration_id != config.id
                or target.generation != body.expected_target_generation or target.current_release_id != body.expected_production_release_id):
                raise ApplicationError('RELEASE_STALE_CONTEXT')
            from f01.release.package import validate_package
            validate_package(artifact.package, artifact.digest)
            row = db.ReleaseIntent(id=uuid4(), project_id=project_id, user_id=owner, auth_session_id=auth_id, artifact_id=artifact.id, configuration_id=config.id,
                version_id=artifact.version_id, brain_revision_id=artifact.brain_revision_id, previous_release_id=target.current_release_id,
                target_generation=target.generation, intent_hash=intent, created_at=now())
            session.add(row)
            session.add(db.ReleaseOperation(id=uuid4(), project_id=project_id, release_id=row.id, state='queued', action='upload', cancel_requested=False,
                epoch=0, attempts=0, next_attempt_at=now(), created_at=now(), deadline_at=now()+timedelta(seconds=settings.release_timeout_seconds)))
            session.flush()
            append_event(session, project, type='release.queued', message='Owner approved this exact production package for deployment.', actor=owner)
        saved.response_body = {'id': str(row.id)}
        return detail(session, row)


def cancel(database: Database, owner: UUID, project_id: UUID, release_id: UUID) -> dto.ReleaseDetail:
    with database.session() as session, session.begin():
        owned_project(session, owner, project_id, lock=True)
        row = session.get(db.ReleaseIntent, release_id)
        if not row or row.project_id != project_id:
            raise ApplicationError('NOT_FOUND')
        op = session.scalar(select(db.ReleaseOperation).where(db.ReleaseOperation.release_id == release_id))
        assert op is not None
        if op.state not in TERMINAL:
            op.cancel_requested = True
            if op.action == 'upload' and op.lease_token is None:
                op.state = 'canceled'
        return detail(session, row)


def workspace(database: Database, settings: Settings, owner: UUID, project_id: UUID) -> dto.ReleaseWorkspace:
    with database.session(snapshot=True) as session:
        owned_project(session, owner, project_id)
        target = session.scalar(select(db.ProductionTarget).where(db.ProductionTarget.project_id == project_id))
        config = session.get(db.ReleaseConfiguration, target.configuration_id) if target else None
        return dto.ReleaseWorkspace(available=settings.release_enabled and config is not None, setup_available=settings.release_enabled,
            hosting_setup=dto.HostingSetup.model_validate(setup) if (setup := session.scalar(select(db.TargetProvisioning).where(db.TargetProvisioning.project_id == project_id))) else None,
            configuration=dto.ProductionConfiguration.model_validate(config) if config else None,
            target_generation=target.generation if target else 0, current_release_id=target.current_release_id if target else None,
            preparations=[preparation(x) for x in session.scalars(select(db.ArtifactPreparation).where(db.ArtifactPreparation.project_id == project_id).order_by(db.ArtifactPreparation.created_at.desc()).limit(30))],
            artifacts=[dto.ReleaseArtifact.model_validate(x) for x in session.scalars(select(db.ReleaseArtifact).where(db.ReleaseArtifact.project_id == project_id).order_by(db.ReleaseArtifact.created_at.desc()).limit(30))],
            releases=[detail(session, x) for x in session.scalars(select(db.ReleaseIntent).where(db.ReleaseIntent.project_id == project_id).order_by(db.ReleaseIntent.created_at.desc()).limit(50))])


def setup_target(database: Database, settings: Settings, owner: UUID, project_id: UUID, body: dto.SetupReleaseTarget, key: str, auth_id: UUID | None) -> dto.HostingSetup:
    with database.session() as session, session.begin():
        lock_owner(session, owner)
        project = owned_project(session, owner, project_id, lock=True)
        if not settings.release_enabled:
            raise ApplicationError('RELEASE_UNAVAILABLE')
        saved, replay = receipt(session, owner, project_id, key, 'release-target', body.model_dump(mode='json'))
        if replay:
            row = session.get(db.TargetProvisioning, replay)
            assert row
            return dto.HostingSetup.model_validate(row)
        row = session.scalar(select(db.TargetProvisioning).where(db.TargetProvisioning.project_id == project_id))
        if row is None:
            available(session, project, body.expected_brain_revision_id, body.expected_version_id)
            source_for_version(session, project_id, body.expected_version_id)
            row = db.TargetProvisioning(id=uuid4(), project_id=project_id, user_id=owner, auth_session_id=auth_id, version_id=body.expected_version_id,
                brain_revision_id=body.expected_brain_revision_id, provider_name='f01-'+project_id.hex, state='queued', epoch=0, attempts=0,
                created_at=now(), deadline_at=now()+timedelta(seconds=settings.release_timeout_seconds))
            session.add(row)
            session.flush()
            append_event(session, project, type='release.target_queued', message='Production hosting setup requested.', actor=owner)
        saved.response_body = {'id': str(row.id)}
        return dto.HostingSetup.model_validate(row)
