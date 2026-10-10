import test from 'node:test';
import assert from 'node:assert/strict';
import {handleRelease} from '../src/lib/workspace/releases-server.ts';
import {releaseReceipt,releaseReceiptExpired,productionURL} from '../src/lib/workspace/release-receipt.ts';
const id='11111111-1111-4111-8111-111111111111',artifact='22222222-2222-4222-8222-222222222222';
const env={APP_ENV:'test',AUTH_MODE:'development',API_INTERNAL_URL:'http://127.0.0.1:8000',NEXT_PUBLIC_APP_URL:'http://localhost:3000',DEV_API_TOKEN:'synthetic-test-private-token-1234567890'};
const body={artifact_id:artifact,configuration_id:id,expected_brain_revision_id:id,expected_version_id:id,expected_production_release_id:null,expected_target_generation:0};
function request(value=body,origin='http://localhost:3000'){return new Request(`http://localhost:3000/api/v1/projects/${id}/releases`,{method:'POST',headers:{Origin:origin,'Content-Type':'application/json','Idempotency-Key':'stable-release'},body:JSON.stringify(value)});}
test('release gateway freezes package/config/source/production and keeps credentials server-only',async()=>{
 let calls=0;
 const result=await handleRelease(request(),id,'releases',[],env,async(input,init)=>{
  const upstream=input instanceof Request?input:new Request(input,init);calls++;
  assert.equal(upstream.url,`http://127.0.0.1:8000/v1/projects/${id}/releases`);assert.equal(upstream.headers.get('authorization'),`Bearer ${env.DEV_API_TOKEN}`);
  assert.equal(upstream.headers.get('idempotency-key'),'stable-release');assert.deepEqual(await upstream.json(),body);
  return Response.json({id:artifact,project_id:id,state:'queued'},{status:202});
 });
 assert.equal(result.status,202);assert.equal(calls,1);assert.equal(result.headers.get('cache-control'),'no-store');assert.ok(!(await result.text()).includes(env.DEV_API_TOKEN));
});
test('release gateway rejects external destinations, source code, stale-body shape and foreign origins before dispatch',async()=>{
 for(const candidate of [{...body,url:'https://evil.test'}, {...body,command:'deploy'}, {...body,expected_target_generation:-1}, {...body,expected_production_release_id:'invalid'}]){
  const result=await handleRelease(request(candidate),id,'releases',[],env,()=>{throw Error('must not dispatch');});assert.equal(result.status,422);
 }
 assert.equal((await handleRelease(request(body,'https://evil.test'),id,'releases',[],env,()=>{throw Error('must not dispatch');})).status,403);
 assert.equal((await handleRelease(request(),id,'releases',['https://evil.test','cancel'],env)).status,404);
});
test('release receipt recovery preserves exact intent and rejects cross-project, expired and malformed state',()=>{
 const receipt={key:'stable-release',path:`/projects/${id}/releases`,body,created:Date.now()};
 assert.deepEqual(releaseReceipt(receipt,id),receipt);assert.equal(releaseReceipt(receipt,artifact),null);assert.equal(releaseReceipt({...receipt,body:{...body,url:'https://evil.test'}},id),null);
 assert.equal(releaseReceiptExpired({...receipt,created:Date.now()-86400000}),true);
 assert.equal(releaseReceipt({...receipt,created:Infinity},id),null);
});
test('production links allow only observed HTTPS Vercel application origins',()=>{
 assert.equal(productionURL('https://app-123.vercel.app'),'https://app-123.vercel.app');
 for(const value of ['http://app.vercel.app','https://app.vercel.app.evil.test','https://user:token@app.vercel.app','https://app.vercel.app/?token=secret','https://app.vercel.app:443','https://127.0.0.1','javascript:alert(1)'])assert.equal(productionURL(value),null,value);
});
