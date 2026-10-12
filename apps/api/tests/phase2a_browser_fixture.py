"""Test-only RSA OIDC issuer and controlled OpenAI HTTP transport; never a production adapter."""
import asyncio
import base64
import hashlib
import json
import secrets
import time
from collections.abc import AsyncIterator
from urllib.parse import urlencode, parse_qs
import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from f01.config import get_settings
from f01.main import create_app
from f01.providers.factory import get_provider_client

settings=get_settings()
if settings.app_env!='test' or '/f01_test_' not in settings.database_url or settings.auth_mode!='oidc':
    raise RuntimeError('Synthetic identity fixture requires explicit OIDC test mode and disposable storage.')
app=create_app(settings)
key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
pending:dict[str,dict[str,str]]={}
codes:dict[str,dict[str,str]]={}
control={'mode':'success','calls':0}
auth_control={'verified':True}

@app.get('/oidc/jwks')
def jwks() -> dict[str,object]:
    public=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public.update(kid='fixture-rsa',alg='RS256',use='sig')
    return {'keys':[public]}

@app.get('/oidc/authorize')
def authorize(request: Request) -> HTMLResponse:
    values=dict(request.query_params)
    if values.get('redirect_uri')!=settings.oidc_redirect_uri or values.get('client_id')!=settings.oidc_client_id or values.get('code_challenge_method')!='S256':return HTMLResponse('Invalid synthetic authorization request',status_code=400)
    handle=secrets.token_urlsafe(24);pending[handle]=values
    return HTMLResponse(f'<html lang="en"><head><title>Synthetic test identity provider</title></head><body><main><h1>Test identity provider</h1><p>Synthetic browser test only.</p><form method="post" action="/oidc/confirm"><input type="hidden" name="handle" value="{handle}"><button name="subject" value="owner-a">Sign in as test owner A</button><button name="subject" value="owner-b">Sign in as test owner B</button></form></main></body></html>')

@app.post('/oidc/confirm')
async def confirm(request: Request) -> RedirectResponse:
    form=parse_qs((await request.body()).decode());values=pending.pop(form.get('handle',[''])[0],None)
    if values is None:return RedirectResponse('/oidc/authorize',status_code=303)
    subject=form.get('subject',[''])[0]
    if subject not in ('owner-a','owner-b'):return RedirectResponse('/oidc/authorize',status_code=303)
    code=secrets.token_urlsafe(32);codes[code]={**values,'subject':subject}
    return RedirectResponse(settings.oidc_redirect_uri+'?'+urlencode({'state':values['state'],'code':code}),status_code=303)

@app.post('/oidc/token')
async def exchange(request: Request) -> JSONResponse:
    form=parse_qs((await request.body()).decode());values=codes.pop(form.get('code',[''])[0],None)
    verifier=form.get('code_verifier',[''])[0];challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    if values is None or values['code_challenge']!=challenge or form.get('redirect_uri')!=[settings.oidc_redirect_uri] or form.get('client_secret')!=[settings.oidc_client_secret.get_secret_value()]:return JSONResponse({'error':'invalid_grant'},status_code=400)
    now=int(time.time());claims={'iss':settings.oidc_issuer,'sub':values['subject'],'aud':settings.oidc_api_audience,'iat':now,'exp':now+900}
    access=jwt.encode(claims,key,algorithm='RS256',headers={'kid':'fixture-rsa'})
    identity=jwt.encode({**claims,'aud':settings.oidc_client_id,'nonce':values['nonce'],'name':'Test owner '+values['subject'][-1].upper(),'email':values['subject']+'@example.test','email_verified':auth_control['verified']},key,algorithm='RS256',headers={'kid':'fixture-rsa'})
    return JSONResponse({'token_type':'Bearer','access_token':access,'id_token':identity})

async def model(request: httpx.Request) -> httpx.Response:
    calls=control['calls'];assert isinstance(calls,int);control['calls']=calls+1
    data=json.loads(request.content)
    assert data['store'] is False and 'tools' not in data and data['max_output_tokens']==settings.planning_output_tokens
    if control['mode']=='quota':return httpx.Response(429,json={'error':{'code':'insufficient_quota'}})
    if control['mode']=='slow':await asyncio.sleep(4)
    context=json.loads(data['input']);assert context['source']['available'] is False
    assert context['bases']['brain_revision_id'] and context['original_brief']['request_id']
    change=context['kind']=='change'
    plan={'project_title':'Priority change proposal' if change else 'Contextual CRM proposal','product_summary':'Proposed workflow based on the saved project context; no application has been generated.',
        'target_users':['Agency owner'],'core_features':[{'name':'Priority leads' if change else 'Lead records','description':'Proposed scoped workflow for saved requirements.'}],
        'recommended_stack':{'frontend':'Next.js / React','backend':'FastAPI','database':'PostgreSQL','rationale':'Continue the proposed persisted stack.'},
        'implementation_milestones':[{'title':'Review requirements','deliverables':['Confirm acceptance criteria before implementation']} ]}
    output={'plan':plan,'scope':['Add a proposed priority view' if change else 'Plan the saved CRM brief'],'assumptions':['No generated source exists'],'acceptance_criteria':['Review lead prioritization' if change else 'Review the proposed lead workflow'],'out_of_scope':['Code execution and deployment']}
    return httpx.Response(200,json={'status':'completed','output':[{'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':json.dumps(output)}]}]})

async def provider_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(model),timeout=10,trust_env=False) as client:yield client
app.dependency_overrides[get_provider_client]=provider_client

@app.post('/test/planning-mode')
async def set_mode(request: Request) -> JSONResponse:
    if request.headers.get('authorization')!='Bearer '+settings.auth_gateway_token.get_secret_value():return JSONResponse({},status_code=401)
    body=await request.json()
    if body.get('mode') not in ('success','quota','slow'):return JSONResponse({},status_code=422)
    control['mode']=body['mode'];return JSONResponse(control)

@app.get('/test/planning-state')
def state(request: Request) -> JSONResponse:
    if request.headers.get('authorization')!='Bearer '+settings.auth_gateway_token.get_secret_value():return JSONResponse({},status_code=401)
    return JSONResponse(control)


@app.post('/test/auth-state')
async def auth_state(request: Request) -> JSONResponse:
    if request.headers.get('authorization')!='Bearer '+settings.auth_gateway_token.get_secret_value():
        return JSONResponse({},status_code=401)
    body=await request.json()
    if body.get('kind')=='unverified':
        auth_control['verified']=False
    elif body.get('kind')=='verified':
        auth_control['verified']=True
    elif body.get('kind')=='expire':
        from datetime import UTC, datetime, timedelta
        from sqlalchemy import update
        from f01.db.models import AuthSession
        with app.state.database.session() as session, session.begin():
            session.execute(update(AuthSession).values(expires_at=datetime.now(UTC)-timedelta(seconds=1)))
    else:
        return JSONResponse({},status_code=422)
    return JSONResponse({'fixture':'controlled OIDC only; no Google account or email delivery'})
