import test from 'node:test';import assert from 'node:assert/strict';
import {handleBuild} from '../src/lib/workspace/build-server.ts';
import {eventRecord} from '../src/lib/workspace/trace.ts';
import {projectRequest} from '../src/lib/projects/browser.ts';
import {buildReceipt,buildReceiptExpired} from '../src/lib/workspace/build-receipt.ts';
import {isolatedPreviewPath} from '../src/lib/workspace/preview-url.ts';
import {readReceipt,saveReceipt} from '../src/lib/workspace/receipt-storage.ts';
const id='ab56889d-a04c-41bb-831e-429948d34cb8',token='synthetic-m4-token-12345678901234567890';
const env={APP_ENV:'test',DEV_API_TOKEN:token,API_INTERNAL_URL:'http://127.0.0.1:8000',NEXT_PUBLIC_APP_URL:'http://127.0.0.1:3000'};
function request(body,origin='http://127.0.0.1:3000'){return new Request(`http://127.0.0.1:3000/api/v1/projects/${id}/builds`,{method:'POST',headers:{Origin:origin,'Content-Type':'application/json','Idempotency-Key':'build-once',Authorization:'Bearer forged'},body:JSON.stringify(body)});}
test('real build gateway uses generated client and private identity',async()=>{const result=await handleBuild(request({proposal_id:id}),id,[],env,async req=>{assert.equal(req.url,`http://127.0.0.1:8000/v1/projects/${id}/builds`);assert.equal(req.headers.get('authorization'),`Bearer ${token}`);assert.equal(req.headers.get('idempotency-key'),'build-once');assert.deepEqual(await req.json(),{proposal_id:id});return Response.json({id},{status:202,headers:{'Set-Cookie':'secret=1'}});});assert.equal(result.status,202);assert.equal(result.headers.get('set-cookie'),null);});
test('real build gateway rejects model commands, non-JSON bodies and foreign origins',async()=>{let calls=0;const send=async()=>{calls++;return Response.json({});};assert.equal((await handleBuild(request({proposal_id:id,command:'rm -rf /'}),id,[],env,send)).status,422);assert.equal((await handleBuild(new Request(`http://127.0.0.1:3000/api/v1/projects/${id}/builds`,{method:'POST',headers:{Origin:'http://127.0.0.1:3000','Content-Type':'text/plain','Idempotency-Key':'build-once'},body:JSON.stringify({proposal_id:id})}),id,[],env,send)).status,422);assert.equal((await handleBuild(request({proposal_id:id},'https://evil.test'),id,[],env,send)).status,403);assert.equal(calls,0);});
test('uncertain real build retains exact idempotency key across replay',async()=>{const keys=[];for(let n=0;n<2;n++)await handleBuild(request({proposal_id:id}),id,[],env,async req=>{keys.push(req.headers.get('idempotency-key'));throw Error('offline');});assert.deepEqual(keys,['build-once','build-once']);});
test('trace accepts real provenance and preserves simulation labels',()=>{const base={id,project_id:id,sequence:1,type:'execution.build',message:'Build observed.',mode:'real',phase:'verifying',severity:'info',payload:{schema_version:1,execution_phase:'build'}};assert.equal(eventRecord(base,id),true);assert.equal(eventRecord({...base,mode:'simulated'},id),true);assert.equal(eventRecord({...base,mode:'invented'},id),false);});
test('browser JSON build reaches the strict gateway without weakening input validation',async()=>{
 const original=globalThis.fetch;let calls=0;
 globalThis.fetch=async(path,options)=>{assert.equal(path,`/api/v1/projects/${id}/builds`);assert.equal(options.headers.get('Content-Type'),'application/json');assert.ok(options.signal instanceof AbortSignal);return handleBuild(new Request(`http://127.0.0.1:3000${path}`,{...options,headers:{...Object.fromEntries(options.headers),Origin:'http://127.0.0.1:3000'}}),id,[],env,async req=>{calls++;assert.deepEqual(await req.json(),{proposal_id:id});return Response.json({id},{status:202});});};
 try{assert.deepEqual(await projectRequest(`/projects/${id}/builds`,{method:'POST',headers:{'Idempotency-Key':'build-once'},body:JSON.stringify({proposal_id:id})}),{id});assert.equal(calls,1);}finally{globalThis.fetch=original;}
});
test('build receipts remain project-scoped and expired or legacy receipts cannot dispatch',()=>{
 const value={key:id,path:`/projects/${id}/builds`,body:{proposal_id:id},created:Date.now()};assert.deepEqual(buildReceipt(value,id),value);assert.equal(buildReceiptExpired(value),false);assert.equal(buildReceipt({...value,path:'/projects/foreign/builds'},id),null);assert.equal(buildReceipt({...value,body:{proposal_id:id,command:'untrusted'}},id),null);assert.equal(buildReceipt({...value,created:Date.now()+1000},id),null);assert.equal(buildReceiptExpired({...value,created:Date.now()-86400000}),true);assert.equal(buildReceiptExpired({...value,created:undefined}),true);
});
test('unavailable browser storage never turns a confirmed command into a failed command',()=>{
 const descriptor=Object.getOwnPropertyDescriptor(globalThis,'sessionStorage');
 Object.defineProperty(globalThis,'sessionStorage',{configurable:true,get(){throw Error('blocked');}});
 try{assert.equal(readReceipt('command',v=>v),null);assert.equal(saveReceipt('command',{id}),false);assert.equal(saveReceipt('command',null),false);}finally{if(descriptor)Object.defineProperty(globalThis,'sessionStorage',descriptor);else delete globalThis.sessionStorage;}
});
test('real preview URLs fail closed on invalid expiry, cookie host and capability paths',()=>{
 const path=`/p/${id}/${'a'.repeat(43)}/`,expiry=new Date(Date.now()+60000).toISOString();assert.equal(isolatedPreviewPath(`https://preview.example${path}`,expiry,'factory.example'),`https://preview.example${path}`);assert.equal(isolatedPreviewPath(`http://127.0.0.1:3031${path}`,expiry,'localhost'),`http://127.0.0.1:3031${path}`);
 for(const [url,expires,host] of [[`https://preview.example${path}`,'bad','factory.example'],[`https://preview.example${path}`,new Date(0).toISOString(),'factory.example'],[`https://preview.example${path}`,expiry,'preview.example'],[`http://preview.example${path}`,expiry,'factory.example'],[`https://preview.example${path}?token=untrusted`,expiry,'factory.example'],['https://preview.example/p/------------------------------------/'+ 'a'.repeat(43)+'/',expiry,'factory.example']])assert.equal(isolatedPreviewPath(url,expires,host),null);
});
