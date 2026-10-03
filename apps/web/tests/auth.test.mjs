import test from 'node:test';
import assert from 'node:assert/strict';
import {validateEnvironment} from '../src/lib/config/environment.mjs';
import {handleProjectsRequest} from '../src/lib/projects/server.ts';
import {authRoute} from '../src/lib/auth/routes.ts';
import {handleContextPlanning} from '../src/lib/workspace/planning-server.ts';
const secret='synthetic-private-gateway-'+ 'g'.repeat(32),opaque='s'.repeat(43),csrf='c'.repeat(43),binding='b'.repeat(43),jwt='signed.api.token';
const env={APP_ENV:'production',AUTH_MODE:'oidc',AUTH_GATEWAY_TOKEN:secret,API_INTERNAL_URL:'https://api.example.test',NEXT_PUBLIC_APP_URL:'https://factory.example.test'};
function request(path,method='GET',headers={}){return new Request(`https://factory.example.test${path}`,{method,headers:{Host:'factory.example.test',...(method==='POST'?{Origin:'https://factory.example.test'}:{}),...headers}});}
const cookies=`__Host-f01-session=${opaque}; __Host-f01-csrf=${csrf}`;
test('production OIDC gateway never accepts claimed browser identity or forwards it',async()=>{
 assert.equal(validateEnvironment(env).authMode,'oidc');let calls=0;
 const send=async(target,options)=>{calls++;const r=target instanceof Request?target:new Request(target,options);if(r.url.endsWith('/auth/access')){assert.equal(r.headers.get('authorization'),`Bearer ${secret}`);assert.deepEqual(await r.json(),{session:opaque,csrf});return Response.json({access_token:jwt});}assert.equal(r.headers.get('authorization'),`Bearer ${jwt}`);assert.equal(r.headers.get('x-f01-session'),opaque);assert.equal(r.headers.get('x-user-id'),null);return Response.json({principal:{id:'stable-user',identity_mode:'oidc'}});};
 const result=await handleProjectsRequest(request('/api/v1/session','GET',{Cookie:cookies,'X-User-ID':'victim'}),'session',undefined,env,send);assert.equal(result.status,200);assert.equal(calls,2);assert.equal((await result.text()).includes(jwt),false);
});
test('context planning gateway accepts only frozen JSON intent and fixed routes',async()=>{
 const project='11111111-1111-4111-8111-111111111111',source='22222222-2222-4222-8222-222222222222';let dispatches=0;
 const body={kind:'change',request_id:source,base_brain_revision_id:source,base_version_id:null};
 const send=async(target,options)=>{const r=target instanceof Request?target:new Request(target,options);if(r.url.endsWith('/auth/access'))return Response.json({access_token:jwt});dispatches++;assert.equal(r.headers.get('authorization'),`Bearer ${jwt}`);assert.equal(r.headers.get('x-f01-csrf'),csrf);assert.deepEqual(await r.json(),body);return Response.json({id:source,status:'pending'},{status:202});};
 function command(value,type='application/json'){return new Request(`https://factory.example.test/api/v1/projects/${project}/planning/attempts`,{method:'POST',headers:{Host:'factory.example.test',Origin:'https://factory.example.test',Cookie:cookies,'Content-Type':type,'Idempotency-Key':'frozen-plan-command'},body:JSON.stringify(value)});}
 assert.equal((await handleContextPlanning(command(body),project,['attempts'],env,send)).status,202);
 assert.equal((await handleContextPlanning(command(body,'text/plain'),project,['attempts'],env,send)).status,422);
 assert.equal((await handleContextPlanning(command({...body,tools:['execute']}),project,['attempts'],env,send)).status,422);
 assert.equal((await handleContextPlanning(command(body),project,['execute'],env,send)).status,404);
 assert.equal(dispatches,1);
});
test('missing or expired session returns no data and never falls back to development owner',async()=>{
 let calls=0;const send=async()=>{calls++;return Response.json({private:'discard'}, {status:401});};
 const missing=await handleProjectsRequest(request('/api/v1/session'),'session',undefined,env,send);assert.equal(missing.status,401);assert.equal(calls,0);
 const expired=await handleProjectsRequest(request('/api/v1/session','GET',{Cookie:cookies}),'session',undefined,env,send);assert.equal(expired.status,401);assert.equal(calls,1);assert.equal((await expired.text()).includes('discard'),false);
});
test('sign-in/callback use secure HttpOnly bound cookies and return no provider token',async()=>{
 const start=await authRoute(request('/api/auth/sign-in','POST'),'sign-in',env,async()=>Response.json({authorization_url:'https://identity.example.test/authorize?state=bound',binding}));assert.equal(start.status,303);const flow=start.headers.get('set-cookie');assert.match(flow,/__Host-f01-login=/);assert.match(flow,/HttpOnly/);assert.match(flow,/Secure/);assert.match(flow,/SameSite=Lax/);assert.match(flow,/Path=\//);assert.doesNotMatch(flow,/Domain=/);
 const callback=await authRoute(request('/api/auth/callback?state=state&code=code','GET',{Cookie:`__Host-f01-login=${binding}`}), 'callback',env,async(target,options)=>{assert.deepEqual(JSON.parse(options.body),{state:'state',code:'code',binding});return Response.json({session:opaque,csrf,expires_at:new Date(Date.now()+300000).toISOString()});});assert.equal(callback.status,303);assert.equal(callback.headers.get('location'),'https://factory.example.test/projects');assert.match(callback.headers.get('set-cookie'),/__Host-f01-session=/);assert.equal(await callback.text(),'');
});
test('sign-out requires same-origin POST and revokes the server session before clearing cookies',async()=>{
 let calls=0;const send=async(target,options)=>{calls++;assert.deepEqual(JSON.parse(options.body),{session:opaque,csrf});return Response.json({signed_out:true});};
 assert.equal((await authRoute(request('/api/auth/sign-out'),'sign-out',env,send)).status,403);assert.equal((await authRoute(request('/api/auth/sign-out','POST',{Origin:'https://other.test'}),'sign-out',env,send)).status,403);assert.equal(calls,0);
 const result=await authRoute(request('/api/auth/sign-out','POST',{Cookie:cookies}),'sign-out',env,send);assert.equal(calls,1);assert.match(result.headers.get('set-cookie'),/Max-Age=0/);
});
