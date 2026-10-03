"""Real PostgreSQL identity/session, context, publication and allowance boundaries."""
import asyncio
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4
from urllib.parse import urlparse, parse_qs

import httpx
import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, update, text, func
from sqlalchemy.exc import DBAPIError

from f01.application.identity import OIDCVerifier, VerifiedIdentity, resolve_identity, start_login, finish_login, digest, seal, authenticate_session
from f01.application import planning
from f01.application.projects import resolve_principal
from f01.application.runs import cancel_run
from f01.config import Settings
from f01.db.models import AuthSession, ExternalIdentity, PlanningAttempt, PlanningProposal, ProjectRequest, Project, BrainRevision, ProjectVersion, User
from f01.db.session import Database
from f01.domain.context_planning import ContextPlan, PlanInput, PlanningResult
from f01.domain.errors import ApplicationError
from f01.domain.planning import ProjectPlan
from f01.main import create_app
from f01.providers.factory import get_context_provider
from f01.providers.base import ProviderError, ProviderErrorCode

@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537,key_size=2048)

def oidc_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"auth_mode":"oidc","auth_gateway_token":SecretStr("synthetic-gateway-"+"g"*32),"session_encryption_key":SecretStr(Fernet.generate_key().decode()),
        "oidc_issuer":"https://identity.example.test", "oidc_jwks_url":"https://identity.example.test/jwks", "oidc_authorization_url":"https://identity.example.test/authorize",
        "oidc_token_url":"https://identity.example.test/token", "oidc_client_id":"factory-client", "oidc_client_secret":SecretStr("synthetic-client-secret"),
        "oidc_api_audience":"factory-api", "oidc_redirect_uri":"https://factory.example.test/api/auth/callback"})

def token(settings: Settings,key: rsa.RSAPrivateKey,subject: str="owner-a",**overrides: Any) -> str:
    now=int(time.time())
    claims={"iss":settings.oidc_issuer,"sub":subject,"aud":settings.oidc_api_audience,"iat":now,"exp":now+600,**overrides}
    return jwt.encode(claims,key,algorithm="RS256",headers={"kid":"test-key"})

def verifier(settings: Settings,key: rsa.RSAPrivateKey) -> OIDCVerifier:
    result=OIDCVerifier(settings);result._keys={"test-key":jwt.PyJWK.from_json(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))};result._loaded=time.monotonic();return result

def login_headers(database: Database,settings: Settings,key: rsa.RSAPrivateKey,subject: str="owner-a") -> tuple[dict[str,str],UUID]:
    access=token(settings,key,subject)
    principal=resolve_identity(database,verifier(settings,key).access(access))
    opaque,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    sid=uuid4();now=datetime.now(UTC)
    with database.session() as session,session.begin():
        session.add(AuthSession(id=sid,user_id=principal.id,session_hash=digest(opaque),csrf_hash=digest(csrf),access_hash=digest(access),access_encrypted=seal(settings,access),created_at=now,last_seen_at=now,expires_at=now+timedelta(minutes=10)))
    return {"Authorization":"Bearer "+access,"X-F01-Session":opaque,"X-F01-CSRF":csrf},sid

def create(client: TestClient) -> dict[str,Any]:
    response=client.post('/v1/projects',json={'title':'Context CRM','brief':'Build a CRM with property leads, private notes and a sales pipeline.'},headers={'Idempotency-Key':str(uuid4())})
    assert response.status_code==201
    return cast(dict[str,Any],response.json())

def input_for(client: TestClient,created: dict[str,Any],kind: str="initial",request_id: str|None=None) -> PlanInput:
    pid=created['project']['id'];saved=client.get(f'/v1/projects/{pid}/workspace').json()
    return PlanInput(kind=kind,request_id=request_id or created['request_id'],base_brain_revision_id=saved['project']['current_brain_revision_id'],base_version_id=saved['project']['current_version_id'])

def result(project_plan: ProjectPlan) -> PlanningResult:
    return PlanningResult(content=ContextPlan(plan=project_plan,scope=['Propose lead prioritization'],assumptions=['No generated source exists'],acceptance_criteria=['Review the proposed lead workflow'],out_of_scope=['Source execution and deployment']),input_tokens=100,output_tokens=200)

@pytest.mark.parametrize('change',[{'aud':'other-api'},{'iss':'https://wrong-issuer.test'},{'exp':1},{'iat':9999999999},{'sub':''}])
def test_signed_tokens_validate_issuer_audience_expiry_subject(settings: Settings,rsa_key: rsa.RSAPrivateKey,change: dict[str,Any]) -> None:
    configured=oidc_settings(settings);check=verifier(configured,rsa_key)
    with pytest.raises(ApplicationError,match='AUTHENTICATION_REQUIRED'):check.access(token(configured,rsa_key,**change))

def test_none_algorithm_and_bad_signature_rejected(settings: Settings,rsa_key: rsa.RSAPrivateKey) -> None:
    configured=oidc_settings(settings);check=verifier(configured,rsa_key)
    unsafe=jwt.encode({'sub':'owner-a'},key='',algorithm='none')
    with pytest.raises(ApplicationError):check.access(unsafe)
    other=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    with pytest.raises(ApplicationError):check.access(token(configured,other))

def test_login_nonce_authorized_party_and_subject_binding(settings: Settings,rsa_key: rsa.RSAPrivateKey) -> None:
    configured=oidc_settings(settings);check=verifier(configured,rsa_key);access=token(configured,rsa_key)
    identity=token(configured,rsa_key,aud=configured.oidc_client_id,nonce='bound-nonce')
    assert check.login(access,identity,digest('bound-nonce')).subject=='owner-a'
    for invalid in (token(configured,rsa_key,aud=configured.oidc_client_id,nonce='wrong'),token(configured,rsa_key,'other',aud=configured.oidc_client_id,nonce='bound-nonce'),token(configured,rsa_key,aud=[configured.oidc_client_id,'other'],nonce='bound-nonce',azp='other')):
        with pytest.raises(ApplicationError):check.login(access,invalid,digest('bound-nonce'))

def test_explicit_identity_link_preserves_stable_owner_and_never_uses_email(database: Database,settings: Settings,rsa_key: rsa.RSAPrivateKey) -> None:
    configured=oidc_settings(settings);old=resolve_principal(database,'founder-development')
    verified=verifier(configured,rsa_key).access(token(configured,rsa_key))
    linked=resolve_identity(database,verified,existing_user_id=old.id);assert linked.id==old.id
    assert resolve_identity(database,verified).id==old.id
    other=resolve_identity(database,verifier(configured,rsa_key).access(token(configured,rsa_key,'other')))
    assert other.id!=old.id
    with pytest.raises(ApplicationError,match='IDENTITY_LINK_CONFLICT'):resolve_identity(database,verified,existing_user_id=other.id)
    with database.session() as session:assert session.scalar(select(func.count()).select_from(ExternalIdentity))==2

def test_oidc_session_authorization_csrf_logout_and_owner_isolation(project_settings: Settings,database: Database,rsa_key: rsa.RSAPrivateKey) -> None:
    configured=oidc_settings(project_settings)
    app=create_app(configured)
    with TestClient(app) as client:
        app.state.oidc_verifier=verifier(configured,rsa_key)
        headers,sid=login_headers(database,configured,rsa_key);client.headers.update(headers)
        created=create(client);pid=created['project']['id']
        assert client.get('/v1/session').json()['principal']['identity_mode']=='oidc'
        # A claimed browser ID does not become authority.
        client.headers['X-User-ID']=str(uuid4());assert client.get(f'/v1/projects/{pid}').status_code==200
        assert client.post('/v1/projects',headers={'Idempotency-Key':str(uuid4()),'X-F01-CSRF':'wrong'},json={'brief':'Build a private booking application.'}).status_code==401
        other,_=login_headers(database,configured,rsa_key,'other-owner');client.headers.update(other)
        for suffix in ('','/brain','/requests','/versions','/workspace','/events','/runs','/planning/proposals'):
            response=client.get(f'/v1/projects/{pid}{suffix}');assert response.status_code==404;assert 'Context CRM' not in response.text
        assert client.get(f'/v1/projects/{pid}/events/stream').status_code==404
        client.headers.update(headers)
        with database.session() as session,session.begin():session.execute(update(AuthSession).where(AuthSession.id==sid).values(revoked_at=datetime.now(UTC)))
        assert client.get(f'/v1/projects/{pid}').status_code==401
        client.headers['Authorization']='Bearer '+configured.dev_api_token.get_secret_value();assert client.get('/v1/session').status_code==401

def test_idle_and_absolute_expiry_reject_session(database: Database,project_settings: Settings,rsa_key: rsa.RSAPrivateKey) -> None:
    configured=oidc_settings(project_settings);headers,sid=login_headers(database,configured,rsa_key);access=headers['Authorization'][7:]
    with database.session() as session,session.begin():session.execute(update(AuthSession).where(AuthSession.id==sid).values(last_seen_at=datetime.now(UTC)-timedelta(hours=1)))
    with pytest.raises(ApplicationError):authenticate_session(database,configured,verifier(configured,rsa_key),access,headers['X-F01-Session'],None,False)

def test_pkce_browser_binding_single_use_callback(database: Database,project_settings: Settings,rsa_key: rsa.RSAPrivateKey,monkeypatch: pytest.MonkeyPatch) -> None:
    configured=oidc_settings(project_settings);flow=start_login(database,configured);query=parse_qs(urlparse(flow['authorization_url']).query)
    import hashlib,base64
    access=token(configured,rsa_key);identity=token(configured,rsa_key,aud=configured.oidc_client_id,nonce=query['nonce'][0],name='Verified owner')
    async def transport(request: httpx.Request) -> httpx.Response:
        form=parse_qs(request.content.decode());challenge=base64.urlsafe_b64encode(hashlib.sha256(form['code_verifier'][0].encode()).digest()).rstrip(b'=').decode()
        assert challenge==query['code_challenge'][0];assert form['redirect_uri'][0]==configured.oidc_redirect_uri
        return httpx.Response(200,json={'access_token':access,'id_token':identity,'token_type':'Bearer'})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(transport),**kwargs))
    check=verifier(configured,rsa_key)
    with pytest.raises(ApplicationError):asyncio.run(finish_login(database,configured,check,query['state'][0],'wrong-binding','code'))
    session=asyncio.run(finish_login(database,configured,check,query['state'][0],flow['binding'],'code'));assert 'access_token' not in session
    with pytest.raises(ApplicationError):asyncio.run(finish_login(database,configured,check,query['state'][0],flow['binding'],'code'))

def test_bounded_context_and_immutable_proposal_do_not_advance_brain_or_versions(client: TestClient,database: Database,project_settings: Settings,project_plan: ProjectPlan) -> None:
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id']);body=input_for(client,created)
    before=client.get(f'/v1/projects/{pid}/workspace').json()
    attempt,prompt=planning.reserve(database,project_settings,uid,str(uuid4()),'hash',pid,body)
    assert prompt and len(prompt.encode())<=project_settings.planning_context_bytes
    assert attempt.reserved_tokens >= len(prompt.encode()) + len(planning.encode(ContextPlan.model_json_schema()).encode()) + project_settings.planning_output_tokens
    context=json.loads(prompt);assert context['original_brief']['request_id']==created['request_id'];assert context['source']['available'] is False
    assert context['requirements'][0]['provenance']['source']=='user_request';assert 'synthetic-provider-credential' not in prompt
    assert context['stack']['frontend']['provenance']['source']=='template'
    assert context['current_plan'][0]['status']=='proposed'
    published=planning.finish(database,project_settings,uid,attempt.id,result(project_plan));assert published.proposal
    after=client.get(f'/v1/projects/{pid}/workspace').json()
    assert after['current_brain']==before['current_brain'];assert after['current_version']==before['current_version'];assert after['project']['lifecycle']==before['project']['lifecycle']
    assert planning.review(database,uid,pid,published.proposal.id).reviewed
    with pytest.raises(DBAPIError),database.engine.begin() as connection:connection.execute(text('UPDATE planning_proposals SET content=\'{}\' WHERE id=:id'),{'id':published.proposal.id})

def test_change_plan_requires_saved_current_request_and_keeps_original(client: TestClient,database: Database,project_settings: Settings,project_plan: ProjectPlan) -> None:
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id'])
    cancel_run(database,uid,pid,UUID(created['run_id']))
    body=input_for(client,created)
    recorded=client.post(f'/v1/projects/{pid}/requests',headers={'Idempotency-Key':str(uuid4())},json={'text':'Add a priority workflow for existing property leads.','base_brain_revision_id':str(body.base_brain_revision_id),'base_version_id':None}).json()
    change=input_for(client,created,'change',recorded['id']);attempt,prompt=planning.reserve(database,project_settings,uid,str(uuid4()),'change',pid,change)
    assert prompt and json.loads(prompt)['kind']=='change';assert 'priority workflow' in prompt
    published=planning.finish(database,project_settings,uid,attempt.id,result(project_plan));assert published.proposal and published.proposal.request_id==UUID(recorded['id'])
    requests=client.get(f'/v1/projects/{pid}/requests').json()['items'];assert next(item for item in requests if item['kind']=='initial')['text']=='Build a CRM with property leads, private notes and a sales pipeline.'

def test_stale_publication_and_review_reject_context_change(client: TestClient,database: Database,project_settings: Settings,project_plan: ProjectPlan) -> None:
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id']);body=input_for(client,created)
    attempt,_=planning.reserve(database,project_settings,uid,str(uuid4()),'stale',pid,body)
    project=client.get(f'/v1/projects/{pid}');client.patch(f'/v1/projects/{pid}',headers={'If-Match':project.headers['etag']},json={'title':'Updated name'})
    discarded=planning.finish(database,project_settings,uid,attempt.id,result(project_plan));assert discarded.status=='stale' and discarded.proposal is None
    next_attempt,_=planning.reserve(database,project_settings,uid,str(uuid4()),'fresh',pid,body);published=planning.finish(database,project_settings,uid,next_attempt.id,result(project_plan));assert published.proposal
    project=client.get(f'/v1/projects/{pid}');client.patch(f'/v1/projects/{pid}',headers={'If-Match':project.headers['etag']},json={'title':'Another name'})
    with pytest.raises(ApplicationError,match='PLANNING_STALE_CONTEXT'):planning.review(database,uid,pid,published.proposal.id)

def test_budget_serialization_failure_accounting_idempotency_and_deadline(client: TestClient,database: Database,project_settings: Settings,project_plan: ProjectPlan) -> None:
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id']);body=input_for(client,created);key=str(uuid4())
    attempt,prompt=planning.reserve(database,project_settings,uid,key,'same',pid,body);assert prompt
    replay,no_prompt=planning.reserve(database,project_settings,uid,key,'same',pid,body);assert replay.id==attempt.id and no_prompt is None
    with pytest.raises(ApplicationError,match='IDEMPOTENCY_KEY_REUSED'):planning.reserve(database,project_settings,uid,key,'other',pid,body)
    with pytest.raises(ApplicationError,match='PLANNING_IN_PROGRESS'):planning.reserve(database,project_settings,uid,str(uuid4()),'other',pid,body)
    planning.finish(database,project_settings,uid,attempt.id,None,'PROVIDER_TIMEOUT')
    limited=project_settings.model_copy(update={'planning_requests_per_day':1})
    with pytest.raises(ApplicationError,match='PLANNING_RATE_LIMITED'):planning.reserve(database,limited,uid,str(uuid4()),'new',pid,body)
    budget=project_settings.model_copy(update={'planning_daily_token_budget':attempt.reserved_tokens})
    with pytest.raises(ApplicationError,match='PLANNING_BUDGET_EXCEEDED'):planning.reserve(database,budget,uid,str(uuid4()),'new',pid,body)
    pending,_=planning.reserve(database,project_settings,uid,str(uuid4()),'restart',pid,body)
    with database.session() as session,session.begin():session.execute(update(PlanningAttempt).where(PlanningAttempt.id==pending.id).values(deadline_at=datetime.now(UTC)-timedelta(seconds=1)))
    assert planning.read_attempt(database,uid,pid,pending.id).status=='abandoned'

def test_cancel_success_publication_race_is_single_terminal(client: TestClient,database: Database,project_settings: Settings,project_plan: ProjectPlan) -> None:
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id']);body=input_for(client,created)
    attempt,_=planning.reserve(database,project_settings,uid,str(uuid4()),'race',pid,body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(planning.read_attempt,database,uid,pid,attempt.id,True);two=pool.submit(planning.finish,database,project_settings,uid,attempt.id,result(project_plan));one.result();two.result()
    final=planning.read_attempt(database,uid,pid,attempt.id);assert final.status in ('succeeded','canceled');assert (final.proposal is not None)==(final.status=='succeeded')

def test_context_route_provider_failure_and_contract(client: TestClient,database: Database,project_settings: Settings,project_plan: ProjectPlan) -> None:
    created=create(client);pid=created['project']['id'];body=input_for(client,created)
    class Fake:
        async def create_context_plan(self,context_json: str,maximum_output_tokens: int) -> PlanningResult:
            assert maximum_output_tokens==3000;assert json.loads(context_json)['project_id']==pid
            return result(project_plan)
    cast(Any,client.app).dependency_overrides[get_context_provider]=lambda:Fake()
    response=client.post(f'/v1/projects/{pid}/planning/attempts',headers={'Idempotency-Key':str(uuid4())},json=body.model_dump(mode='json'));assert response.status_code==202
    outcome=client.get(f'/v1/projects/{pid}/planning/attempts/{response.json()["id"]}').json();assert outcome['status']=='succeeded'
    class Failure:
        async def create_context_plan(self,context_json: str,maximum_output_tokens: int) -> PlanningResult:raise ProviderError(ProviderErrorCode.QUOTA)
    cast(Any,client.app).dependency_overrides[get_context_provider]=lambda:Failure()
    response=client.post(f'/v1/projects/{pid}/planning/attempts',headers={'Idempotency-Key':str(uuid4())},json=body.model_dump(mode='json'))
    outcome=client.get(f'/v1/projects/{pid}/planning/attempts/{response.json()["id"]}').json();assert outcome['status']=='failed' and outcome['error_code']=='PROVIDER_QUOTA_EXCEEDED'

def test_additive_migration_preserves_phase1_records(client: TestClient,database: Database) -> None:
    created=create(client);config=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    with database.engine.begin() as connection:
        config.attributes['connection']=connection
        command.downgrade(config,'0001_phase1')
        assert connection.execute(text('SELECT id FROM projects WHERE id=:id'),{'id':created['project']['id']}).scalar() == UUID(created['project']['id'])
        command.upgrade(config,'head')
    saved=client.get(f'/v1/projects/{created["project"]["id"]}/workspace').json();assert saved['current_brain']['id']==created['brain_revision_id']

@pytest.mark.parametrize('invalid',['issuer','key','gateway','audience'])
def test_production_oidc_configuration_fails_closed(settings:Settings,invalid:str) -> None:
    values=oidc_settings(settings).model_dump();values['app_env']='production'
    assert Settings.model_validate(values).auth_mode=='oidc'
    field,value={'issuer':('oidc_issuer','http://identity.example.test'),'key':('session_encryption_key','invalid'),'gateway':('auth_gateway_token','short'),'audience':('oidc_api_audience','')}[invalid]
    values[field]=value
    with pytest.raises(ValidationError):Settings.model_validate(values)

@pytest.mark.parametrize('state',['revoked','idle','expired'])
def test_session_ending_during_plan_discards_result(database:Database,project_settings:Settings,rsa_key:rsa.RSAPrivateKey,project_plan:ProjectPlan,state:str) -> None:
    configured=oidc_settings(project_settings);app=create_app(configured)
    with TestClient(app) as client:
        app.state.oidc_verifier=verifier(configured,rsa_key);headers,sid=login_headers(database,configured,rsa_key);client.headers.update(headers)
        created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id']);body=input_for(client,created)
        attempt,_=planning.reserve(database,configured,uid,str(uuid4()),'auth-ending',pid,body)
        field={'revoked':'revoked_at','idle':'last_seen_at','expired':'expires_at'}[state]
        with database.session() as session,session.begin():session.execute(update(AuthSession).where(AuthSession.id==sid).values(**{field:datetime.now(UTC)-timedelta(hours=1)}))
        final=planning.finish(database,configured,uid,attempt.id,result(project_plan),auth_session_id=sid)
        assert final.status=='failed' and final.error_code=='AUTHENTICATION_REQUIRED' and final.proposal is None

def test_concurrent_usage_reservations_allow_one_provider_dispatch(client:TestClient,database:Database,project_settings:Settings) -> None:
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id']);body=input_for(client,created)
    def reserve_one() -> str:
        try:
            _,prompt=planning.reserve(database,project_settings,uid,str(uuid4()),'parallel',pid,body)
            assert prompt;return 'dispatch'
        except ApplicationError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(lambda _:reserve_one(),range(2)))
    assert sorted(outcomes)==['PLANNING_IN_PROGRESS','dispatch']
    usage=planning.usage(database,project_settings,uid);assert usage.requests_used==1 and usage.tokens_reserved>0

def test_context_wrong_bases_foreign_request_and_utf8_bounds(client:TestClient,database:Database,project_settings:Settings) -> None:
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id']);body=input_for(client,created)
    for field in ('base_brain_revision_id','base_version_id'):
        with pytest.raises(ApplicationError,match='PLANNING_STALE_CONTEXT'):planning.reserve(database,project_settings,uid,str(uuid4()),'wrong-base',pid,body.model_copy(update={field:uuid4()}))
    other=create(client)
    with pytest.raises(ApplicationError,match='NOT_FOUND'):planning.reserve(database,project_settings,uid,str(uuid4()),'foreign-request',pid,body.model_copy(update={'request_id':UUID(other['request_id'])}))
    clipped=planning.excerpt('你好🙂'*3000,1001);assert clipped['truncated'] and len(str(clipped['text']).encode())<=1001
    assert '\ufffd' not in str(clipped['text'])
    long=client.post('/v1/projects',headers={'Idempotency-Key':str(uuid4())},json={'title':'Long context','brief':'你好🙂'*3000}).json()
    _,prompt=planning.reserve(database,project_settings,uid,str(uuid4()),'long-context',UUID(long['project']['id']),input_for(client,long))
    assert prompt and len(prompt.encode())<=project_settings.planning_context_bytes
    assert json.loads(prompt)['selection']['context_truncated'] is True

def test_jwks_cache_unknown_key_and_fetch_failure_are_bounded(settings:Settings,rsa_key:rsa.RSAPrivateKey,monkeypatch:pytest.MonkeyPatch) -> None:
    configured=oidc_settings(settings);real_client=httpx.Client;calls=[]
    jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key()));jwk['kid']='test-key'
    def handler(request:httpx.Request) -> httpx.Response:
        calls.append(request.url);assert str(request.url)==configured.oidc_jwks_url
        return httpx.Response(200,json={'keys':[jwk]})
    monkeypatch.setattr('f01.application.identity.httpx.Client',lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    check=OIDCVerifier(configured);assert check.access(token(configured,rsa_key)).subject=='owner-a';assert check.access(token(configured,rsa_key)).subject=='owner-a'
    with pytest.raises(ApplicationError):check._key('unrecognized-key')
    assert len(calls)==1
    check._loaded=-1000;check._last_fetch=-1000
    monkeypatch.setattr('f01.application.identity.httpx.Client',lambda **kwargs:real_client(transport=httpx.MockTransport(lambda r:httpx.Response(503)),**kwargs))
    with pytest.raises(ApplicationError):check.access(token(configured,rsa_key))

def test_revoked_session_stream_sends_no_replay_data(client:TestClient,database:Database,project_settings:Settings) -> None:
    from f01.api.stream import stream_events
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id'])
    async def disconnected() -> bool:return False
    async def run() -> None:
        frames=[frame async for frame in stream_events(database,uid,pid,0,project_settings,'unused',disconnected,authorized=lambda:False)]
        assert len(frames)==1 and 'session_expired' in frames[0] and 'Context CRM' not in frames[0]
    asyncio.run(run())

def test_planning_locks_allow_existing_fk_writes_and_expired_replay_cancel(client:TestClient,database:Database,project_settings:Settings) -> None:
    created=create(client);pid=UUID(created['project']['id']);uid=UUID(created['project']['owner_user_id']);body=input_for(client,created);key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        with database.engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='2s'"))
            connection.execute(text('SELECT id FROM projects WHERE id=:id FOR UPDATE'),{'id':pid})
            future=pool.submit(planning.reserve,database,project_settings,uid,key,'lock-order',pid,body)
            blocked=False
            for _ in range(100):
                connection.execute(text('SELECT pg_stat_clear_snapshot()'))
                blocked=bool(connection.execute(text("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND query ILIKE '%projects%' AND pid<>pg_backend_pid()")).scalar())
                if blocked:break
                time.sleep(.01)
            assert blocked,'Reservation must hold owner serialization while waiting for project'
            # Existing request/idempotency FK inserts take this lock while holding project.
            assert connection.execute(text('SELECT id FROM users WHERE id=:id FOR KEY SHARE'),{'id':uid}).scalar()==uid
        saved,prompt=future.result(timeout=5);assert prompt
        with database.session() as session,session.begin():session.execute(update(PlanningAttempt).where(PlanningAttempt.id==saved.id).values(deadline_at=datetime.now(UTC)-timedelta(seconds=1)))
        replay=pool.submit(planning.reserve,database,project_settings,uid,key,'lock-order',pid,body)
        cancel=pool.submit(planning.read_attempt,database,uid,pid,saved.id,True)
        assert replay.result(timeout=5)[0].status=='abandoned' and cancel.result(timeout=5).status=='abandoned'
