"""Real PostgreSQL transaction, replay, recovery and command invariants."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4
from typing import Any, cast
from sqlalchemy.orm import Session
from f01.db.session import Database
from f01.config import Settings
from f01.domain.projects import RunRecord

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from f01.api.stream import stream_events, replay_cursor
from f01.application.projects import read_events, workspace, resolve_principal
from f01.application.runs import cancel_run, read_run, start_run, retry_run
from f01.db.models import BrainRevision, BuildEvent, BuildRun, DeploymentRecord, Project, ProjectRequest, ProjectVersion
from f01.domain.errors import ApplicationError
from f01.domain.projects import StartRun
from f01.execution.runner import SimulationRunner
from f01.main import create_app


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC) + timedelta(seconds=1)
    def __call__(self) -> datetime:
        return self.now
    def forward(self) -> None:
        self.now += timedelta(seconds=1)


def create(client: TestClient) -> dict[str, Any]:
    response = client.post('/v1/projects', headers={'Idempotency-Key': str(uuid4())}, json={'title':'M5 CRM','brief':'Build a CRM with leads, notes and a sales pipeline.'})
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


def owner(database: Database, created: dict[str, Any]) -> UUID:
    with database.session() as session:
        project = session.get(Project, UUID(created['project']['id']))
        assert project is not None
        return project.owner_user_id


def complete(database: Database, run_id: UUID, clock: Clock) -> None:
    runner = SimulationRunner(database, clock=clock)
    for _ in range(12):
        runner.advance(run_id)
        clock.forward()
        with database.session() as session:
            run = session.get(BuildRun, run_id)
            assert run is not None
            if run.status not in ('queued','running'):
                return
    raise AssertionError('Fixture did not terminate')


def change(client: TestClient, project_id: UUID, text: str = 'Add a priority filter to the saved CRM leads.') -> dict[str, Any]:
    current = client.get(f'/v1/projects/{project_id}/workspace').json()
    response = client.post(f'/v1/projects/{project_id}/requests', headers={'Idempotency-Key':str(uuid4())}, json={'text':text,
        'base_brain_revision_id':current['project']['current_brain_revision_id'],'base_version_id':current['project']['current_version_id']})
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


def counts(session: Session, project_id: UUID) -> tuple[int, ...]:
    return tuple(cast(int,session.scalar(select(func.count()).select_from(model).where(model.project_id == project_id))) for model in (BrainRevision, ProjectVersion, DeploymentRecord))


@pytest.mark.parametrize('name,expected', [('crm-success','succeeded'),('generic-success','succeeded'),('recoverable-verification','succeeded'),('terminal-failure','failed')])
def test_versioned_scenarios_controlled_clock(database: Database, client: TestClient, name: str, expected: str) -> None:
    created=create(client); pid=UUID(created['project']['id']); uid=owner(database,created); clock=Clock()
    cancel_run(database,uid,pid,UUID(created['run_id']))
    request=change(client,pid)
    run=start_run(database,uid,pid,StartRun(request_id=request['id'],expected_brain_revision_id=created['brain_revision_id']),str(uuid4()),change_scenario=name,now=clock.now)
    runner=SimulationRunner(database,clock=clock)
    assert runner.advance(run.id)
    before=workspace(database,uid,pid)
    assert not runner.advance(run.id)
    assert workspace(database,uid,pid).last_sequence == before.last_sequence
    assert before.active_run is not None
    assert before.active_run.phase == 'understanding'
    clock.forward(); complete(database,run.id,clock)
    final=workspace(database,uid,pid)
    assert final.latest_run is not None
    assert final.latest_run.status == expected
    events=read_events(database,uid,pid,0,100).items
    assert [e.sequence for e in events] == list(range(1,final.last_sequence+1))
    assert all(e.mode == 'simulated' and e.message.startswith('Simulation:') for e in events if e.payload.step_cursor is not None)
    assert all(e.payload.event_index is not None for e in events if e.payload.step_cursor is not None)
    if expected == 'succeeded':
        assert final.current_version and final.current_brain.source_run_id == run.id
        assert final.current_brain.content.original_request_id == UUID(created['request_id'])
        assert final.current_brain.content.product.requirements[0].requirement_id == 'req-001'
        assert final.current_brain.content.product.requirements[-1].provenance.request_id == UUID(request['id'])
        with database.session() as session:
            assert counts(session,pid) == (2,1,1)
            deployment=session.scalar(select(DeploymentRecord).where(DeploymentRecord.project_id==pid))
            assert deployment is not None
            assert deployment.version_id==final.current_version.id and deployment.external_url is None
    else:
        assert final.current_version is None and final.current_brain.id == UUID(created['brain_revision_id'])
    if name == 'recoverable-verification':
        issue=next(e for e in events if e.type=='verification.failed')
        repair=next(e for e in events if e.type=='repair.recorded')
        assert issue.sequence < repair.sequence and issue.payload.issue_id == repair.payload.resolves_issue_id
        phases=[e.phase for e in events if e.type=='run.phase_changed']
        assert phases==['understanding','planning','building','verifying','building','verifying','deploying']


def test_atomic_publication_rolls_back_and_restart_resumes(database: Database, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    created=create(client); uid=owner(database,created); pid=UUID(created['project']['id']); rid=UUID(created['run_id']); clock=Clock()
    runner=SimulationRunner(database,clock=clock)
    for _ in range(5): assert runner.advance(rid); clock.forward()
    before=workspace(database,uid,pid)
    original=runner.publish
    def failing(*args: Any) -> None:
        original(*args)
        raise RuntimeError('injected transaction failure')
    monkeypatch.setattr(runner,'publish',failing)
    with pytest.raises(RuntimeError): runner.advance(rid)
    after=workspace(database,uid,pid)
    assert after==before
    with database.session() as session: assert counts(session,pid)==(1,0,0)
    restarted=SimulationRunner(database,clock=clock)
    assert restarted.advance(rid)
    assert not restarted.advance(rid)
    final=workspace(database,uid,pid)
    assert final.current_version and final.current_brain.revision==2
    assert final.current_version.brain_revision_id==final.current_brain.id
    assert final.current_version.id in final.current_brain.content.history.version_ids
    with database.session() as session:
        initial=session.get(BrainRevision,UUID(created['brain_revision_id']))
        assert initial is not None
        assert cast(dict[str, Any], initial.content['history'])['version_ids']==[]
        keys=session.scalars(select(BuildEvent.deduplication_key).where(BuildEvent.run_id==rid,BuildEvent.deduplication_key.is_not(None))).all()
        assert len(keys)==len(set(keys))


def test_concurrent_duplicate_final_step_publishes_once(database: Database, client: TestClient) -> None:
    created=create(client); rid=UUID(created['run_id']); pid=UUID(created['project']['id']); clock=Clock(); runner=SimulationRunner(database,clock=clock)
    for _ in range(5): runner.advance(rid); clock.forward()
    barrier=Barrier(6)
    def tick() -> bool: barrier.wait(); return SimulationRunner(database,clock=clock).advance(rid)
    with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(lambda _:tick(),range(6)))
    assert sum(results)==1
    with database.session() as session:
        assert counts(session,pid)==(2,1,1)
        assert session.scalar(select(func.count()).select_from(BuildEvent).where(BuildEvent.run_id==rid,BuildEvent.type=='run.succeeded'))==1


@pytest.mark.parametrize('_',range(5))
def test_success_cancel_race_one_terminal_result(database: Database, client: TestClient, _: int) -> None:
    created=create(client); rid=UUID(created['run_id']); pid=UUID(created['project']['id']); uid=owner(database,created); clock=Clock(); runner=SimulationRunner(database,clock=clock)
    for step in range(5): runner.advance(rid); clock.forward()
    barrier=Barrier(2)
    def succeed() -> bool: barrier.wait(); return runner.advance(rid)
    def cancel() -> RunRecord: barrier.wait(); return cancel_run(database,uid,pid,rid,now=clock.now)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(succeed); b=pool.submit(cancel); a.result(); b.result()
    state=workspace(database,uid,pid)
    assert state.latest_run is not None
    assert state.latest_run.status in ('succeeded','canceled')
    with database.session() as session:
        assert counts(session,pid)==((2,1,1) if state.latest_run.status=='succeeded' else (1,0,0))
        terminal=session.scalars(select(BuildEvent).where(BuildEvent.run_id==rid,BuildEvent.type.in_(['run.succeeded','run.canceled']))).all()
        assert len(terminal)==1
    seq=state.last_sequence
    cancel_run(database,uid,pid,rid)
    assert workspace(database,uid,pid).last_sequence==seq
    assert not runner.advance(rid)


def test_failed_update_retry_preserves_preview_and_inputs(database: Database, client: TestClient) -> None:
    created=create(client); uid=owner(database,created); pid=UUID(created['project']['id']); clock=Clock()
    complete(database,UUID(created['run_id']),clock)
    prior=workspace(database,uid,pid); assert prior.current_version is not None; request=change(client,pid)
    input=StartRun(request_id=request['id'],expected_brain_revision_id=prior.current_brain.id)
    run=start_run(database,uid,pid,input,'start-update',change_scenario='terminal-failure',now=clock.now)
    replay=start_run(database,uid,pid,input,'start-update',now=clock.now)
    assert replay.id==run.id
    complete(database,run.id,clock)
    failed=workspace(database,uid,pid)
    assert failed.current_version==prior.current_version and failed.current_brain==prior.current_brain
    assert failed.project.lifecycle=='error'
    retry=retry_run(database,uid,pid,run.id,'retry-update',now=clock.now)
    assert retry.retry_of_run_id==run.id and retry.attempt==2
    assert (retry.request_id,retry.input_brain_revision_id,retry.base_version_id)==(run.request_id,run.input_brain_revision_id,run.base_version_id)
    complete(database,retry.id,clock)
    assert retry_run(database,uid,pid,run.id,'retry-update',now=clock.now).id==retry.id
    success=workspace(database,uid,pid)
    assert success.current_version is not None
    assert success.current_version.number==2 and success.current_version.preview_descriptor==prior.current_version.preview_descriptor
    assert any(str(run.id) in issue for issue in success.current_brain.content.history.issue_ids)
    path=f'/v1/projects/{pid}'
    first_page=client.get(path+'/deployments',params={'limit':1}).json()
    assert len(first_page['items'])==1 and first_page['next_cursor']
    second_page=client.get(path+'/deployments',params={'limit':1,'cursor':first_page['next_cursor']}).json()
    assert len(second_page['items'])==1 and second_page['items'][0]['id']!=first_page['items'][0]['id']
    run_page=client.get(path+'/runs',params={'limit':1}).json()
    assert len(run_page['items'])==1 and run_page['next_cursor']
    assert read_run(database,uid,pid,run.id).status=='failed'
    with database.session() as session:
        original_request=session.get(ProjectRequest,UUID(created['request_id']))
        assert original_request is not None and original_request.text=='Build a CRM with leads, notes and a sales pipeline.'
        assert counts(session,pid)==(3,2,2)
    with pytest.raises(ApplicationError,match='STALE_BRAIN_REVISION'): retry_run(database,uid,pid,run.id,'new-stale-retry',now=clock.now)
    with pytest.raises(ApplicationError,match='STALE_BRAIN_REVISION'): start_run(database,uid,pid,input,'stale-start',now=clock.now)


def test_cancel_queued_and_update_returns_idle_or_prior_live(database: Database, client: TestClient) -> None:
    created=create(client); uid=owner(database,created); pid=UUID(created['project']['id']); rid=UUID(created['run_id']); clock=Clock()
    cancel_run(database,uid,pid,rid)
    assert workspace(database,uid,pid).project.lifecycle=='idle'
    with pytest.raises(ApplicationError,match='RUN_NOT_RETRYABLE'): retry_run(database,uid,pid,rid,'bad-retry')
    request=change(client,pid); first=start_run(database,uid,pid,StartRun(request_id=request['id'],expected_brain_revision_id=created['brain_revision_id']),'first',now=clock.now)
    complete(database,first.id,clock); prior=workspace(database,uid,pid); assert prior.current_version is not None; request=change(client,pid)
    run=start_run(database,uid,pid,StartRun(request_id=request['id'],expected_brain_revision_id=prior.current_brain.id),'next',now=clock.now)
    SimulationRunner(database,clock=clock).advance(run.id)
    cancel_run(database,uid,pid,run.id,now=clock.now)
    final=workspace(database,uid,pid)
    assert final.project.lifecycle=='live' and final.current_version==prior.current_version


def test_run_commands_ownership_idempotency_stale_version_and_active(database: Database, client: TestClient) -> None:
    created=create(client); uid=owner(database,created); pid=UUID(created['project']['id']); clock=Clock()
    complete(database,UUID(created['run_id']),clock)
    request=change(client,pid); other=change(client,pid,'Add another saved change with the same context.')
    body={'request_id':request['id'],'expected_brain_revision_id':request['base_brain_revision_id']}
    path=f'/v1/projects/{pid}/runs'; key={'Idempotency-Key':'command-key'}
    response=client.post(path,json=body,headers=key); assert response.status_code==202
    rid=UUID(response.json()['id'])
    assert client.post(path,json={**body,'request_id':other['id']},headers=key).json()['error']['code']=='IDEMPOTENCY_KEY_REUSED'
    assert client.post(path,json={**body,'request_id':other['id']},headers={'Idempotency-Key':'other-key'}).json()['error']['code']=='ACTIVE_RUN_EXISTS'
    complete(database,rid,clock)
    assert client.post(path,json=body,headers=key).json()['id']==str(rid)
    foreign=resolve_principal(database,'m5-foreign')
    with pytest.raises(ApplicationError,match='NOT_FOUND'): cancel_run(database,foreign.id,pid,rid)
    with pytest.raises(ApplicationError,match='NOT_FOUND'): start_run(database,foreign.id,pid,StartRun(**body),'foreign')
    with database.session() as session, session.begin():
        project=session.get(Project,pid,with_for_update=True)
        assert project is not None
        project.current_brain_revision_id=UUID(other['base_brain_revision_id'])
        project.current_version_id=None
    assert client.post(path,json={**body,'request_id':other['id']},headers={'Idempotency-Key':'stale-version'}).json()['error']['code']=='STALE_BASE_VERSION'
    assert client.post(path,json={**body,'expected_brain_revision_id':str(uuid4())},headers={'Idempotency-Key':'stale-brain'}).json()['error']['code']=='STALE_BRAIN_REVISION'


def test_unknown_scenario_version_terminates_honestly(database: Database, client: TestClient) -> None:
    created=create(client); uid=owner(database,created); pid=UUID(created['project']['id']); clock=Clock()
    cancel_run(database,uid,pid,UUID(created['run_id']))
    rid=uuid4()
    with database.session() as session, session.begin():
        session.add(BuildRun(id=rid,project_id=pid,request_id=UUID(created['request_id']),input_brain_revision_id=UUID(created['brain_revision_id']),
            attempt=1,mode='simulated',status='queued',scenario_id='crm-success',scenario_version=999,step_cursor=0,next_step_at=clock.now,created_at=clock.now))
    assert SimulationRunner(database,clock=clock).tick()==1
    run=read_run(database,uid,pid,rid)
    assert run.status=='failed' and run.error_code=='SCENARIO_VERSION_UNAVAILABLE'
    with database.session() as session: assert counts(session,pid)==(1,0,0)


def test_sse_replay_authorization_expiry_and_cursor_validation(database: Database, client: TestClient, project_settings: Settings) -> None:
    created=create(client); uid=owner(database,created); pid=UUID(created['project']['id']); clock=Clock(); rid=UUID(created['run_id'])
    SimulationRunner(database,clock=clock).advance(rid)
    token=project_settings.dev_api_token.get_secret_value()
    async def connected() -> bool: return False
    async def inspect() -> None:
        generator=stream_events(database,uid,pid,0,project_settings,token,connected,poll_seconds=0)
        assert await anext(generator)==': connected\n\n'
        first=await anext(generator); second=await anext(generator)
        assert 'id: 1\n' in first and 'id: 2\n' in second
        project_settings.dev_token_expires_at=datetime.now(UTC)-timedelta(seconds=1)
        assert 'session_expired' in await anext(generator)
        with pytest.raises(StopAsyncIteration): await anext(generator)
        project_settings.dev_token_expires_at=None
        foreign=resolve_principal(database,'sse-foreign')
        invalid=stream_events(database,foreign.id,pid,0,project_settings,token,connected,poll_seconds=0)
        assert 'access_revoked' in await anext(invalid)
        await invalid.aclose()
        resumed=stream_events(database,uid,pid,2,project_settings,token,connected,poll_seconds=0)
        assert await anext(resumed)==': connected\n\n'
        assert 'id: 3\n' in await anext(resumed)
        await resumed.aclose()
    asyncio.run(inspect())
    assert replay_cursor('0','2')==2
    stream=f'/v1/projects/{pid}/events/stream'
    for cursor in ['-1','bad','2147483648','999']:
        assert client.get(stream,params={'after_sequence':cursor}).status_code==422
    assert client.get(stream,params={'after_sequence':'0'},headers={'Last-Event-ID':'bad'}).status_code==422
    client.headers.pop('Authorization')
    assert client.get(stream).status_code==401
    project_settings.dev_token_expires_at=datetime.now(UTC)-timedelta(seconds=1)
    client.headers['Authorization']=f'Bearer {token}'
    assert client.get(stream).status_code==401


def test_poll_reads_never_progress_and_replay_is_ordered(database: Database, client: TestClient) -> None:
    created=create(client); uid=owner(database,created); pid=UUID(created['project']['id']); clock=Clock()
    before=workspace(database,uid,pid)
    for _ in range(3): read_events(database,uid,pid,0,100)
    assert workspace(database,uid,pid)==before
    complete(database,UUID(created['run_id']),clock)
    cursor=0; sequences: list[int]=[]
    while True:
        page=read_events(database,uid,pid,cursor,2)
        sequences.extend(e.sequence for e in page.items)
        if page.next_cursor is None: break
        cursor=int(page.next_cursor)
    assert sequences==list(range(1,workspace(database,uid,pid).last_sequence+1))
    filtered=client.get(f'/v1/projects/{pid}/events',params={'run_id':created['run_id'],'limit':100})
    assert all(e['run_id']==created['run_id'] for e in filtered.json()['items'])


def test_lifespan_loop_restart_and_read_only_heartbeat(database: Database, project_settings: Settings) -> None:
    import time
    configured=project_settings.model_copy(update={'simulation_runner_enabled':True,'simulation_tick_ms':100})
    with TestClient(create_app(configured)) as first:
        first.headers['Authorization']='Bearer '+configured.dev_api_token.get_secret_value()
        created=create(first); pid=UUID(created['project']['id']); rid=UUID(created['run_id']); uid=owner(database,created)
        for _ in range(100):
            run=read_run(database,uid,pid,rid)
            if run.step_cursor >= 2: break
            time.sleep(.01)
        else: raise AssertionError('Lifespan runner did not progress')
        assert run.step_cursor < 6
        saved=run.step_cursor
    with TestClient(create_app(configured)) as restarted:
        restarted.headers.update(first.headers)
        for _ in range(100):
            run=read_run(database,uid,pid,rid)
            if run.status=='succeeded': break
            time.sleep(.02)
        else: raise AssertionError('Restart did not finish persisted cursor')
        assert run.step_cursor==6 and run.step_cursor>saved
        snapshot=workspace(database,uid,pid)
        assert snapshot.project.metadata_version==1
        assert restarted.get('/v1/session').json()['capabilities']['simulation_runner'] is True
    sequence=snapshot.last_sequence
    async def connected() -> bool: return False
    async def heartbeat() -> None:
        generator=stream_events(database,uid,pid,sequence,configured,configured.dev_api_token.get_secret_value(),connected,poll_seconds=0,heartbeat_seconds=0)
        assert await anext(generator)==': connected\n\n'
        assert await anext(generator)==': heartbeat\n\n'
        await generator.aclose()
    asyncio.run(heartbeat())
    assert workspace(database,uid,pid).last_sequence==sequence

def test_quiet_event_stream_confirms_transport_promptly_without_progress(database:Database,client:TestClient,project_settings:Settings)->None:
    created=create(client);pid=UUID(created['project']['id']);uid=owner(database,created)
    before=workspace(database,uid,pid)
    async def connected()->bool:return False
    async def check()->None:
        generator=stream_events(database,uid,pid,before.last_sequence,project_settings,project_settings.dev_api_token.get_secret_value(),connected)
        try:assert await asyncio.wait_for(anext(generator),timeout=1)==': connected\n\n'
        finally:await generator.aclose()
    asyncio.run(check())
    assert workspace(database,uid,pid)==before
