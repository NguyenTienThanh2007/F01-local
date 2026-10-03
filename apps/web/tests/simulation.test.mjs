import test from 'node:test';
import assert from 'node:assert/strict';
import { acceptEvents, issueRelationships, eventRecord, reconnectDelay } from '../src/lib/workspace/trace.ts';
import { readRunCommand } from '../src/lib/workspace/run-command.ts';
import { handleRunRequest, handleEventStream } from '../src/lib/workspace/run-server.ts';
const id='ab56889d-a04c-41bb-831e-429948d34cb8', run='30fe5cca-25e1-4f68-b80a-6b281d7b5c22';
const token='synthetic-m5-token-12345678901234567890';
const env={APP_ENV:'test',DEV_API_TOKEN:token,API_INTERNAL_URL:'http://127.0.0.1:8000',NEXT_PUBLIC_APP_URL:'http://127.0.0.1:3000'};
const event=(sequence,updates={}) => ({id:crypto.randomUUID(),project_id:id,run_id:run,request_id:id,sequence,type:'step.completed',phase:'building',severity:'info',mode:'simulated',message:'Simulation: fixture selection only.',payload:{schema_version:1},occurred_at:new Date().toISOString(),...updates});
test('sequence gaps hold later events until ordered recovery; duplicates are ignored',() => {
 let state={sequence:1,events:[event(1)],pending:[]}; const fourth=event(4);
 let result=acceptEvents(state,[fourth]); assert.equal(result.gap,true); assert.deepEqual(result.state.events.map(e=>e.sequence),[1]);
 result=acceptEvents(result.state,[event(2),event(3),fourth]); assert.equal(result.gap,false); assert.deepEqual(result.state.events.map(e=>e.sequence),[1,2,3,4]);
 assert.deepEqual(acceptEvents(result.state,[fourth,event(2)]).state,result.state);
});
test('out-of-order batches recover in project sequence and issue repairs stay run scoped',() => {
 const issue=event(1,{type:'verification.failed',payload:{schema_version:1,issue_id:'sample'}});
 const repair=event(3,{type:'repair.recorded',payload:{schema_version:1,resolves_issue_id:'sample'}});
 const other=event(2,{run_id:id,payload:{schema_version:1,resolves_issue_id:'sample'}});
 const result=acceptEvents({sequence:0,events:[],pending:[]},[repair,other,issue]); assert.deepEqual(result.state.events.map(e=>e.sequence),[1,2,3]);
 assert.deepEqual(issueRelationships(result.state.events)[0].repairs,[repair]);
});
test('transport validation rejects foreign, unsafe or invalid records; reconnect is bounded',() => {
 assert.equal(eventRecord(event(1),id),true);
 for (const invalid of [event(0),event(1,{project_id:run}),event(1,{mode:'real'}),event(1,{phase:'fake'}),event(1,{payload:{schema_version:2}})]) assert.equal(eventRecord(invalid,id),false);
 assert.equal(reconnectDelay(0,()=>0),1000); assert.equal(reconnectDelay(10,()=>1),15000);
});
test('unresolved run receipts preserve exact start/retry/cancel context across reload',() => {
 for (const action of ['start','retry','cancel']) {
  const command={action,key:run,started:Date.now(),input:action==='start'?{request_id:id,expected_brain_revision_id:run}:{},...(action==='start'?{}:{runId:id})};
  assert.deepEqual(readRunCommand({getItem:()=>JSON.stringify(command)},'receipt'),command);
  assert.equal(readRunCommand({getItem:()=>JSON.stringify({...command,key:'bad'})},'receipt'),null);
 }
 assert.equal(readRunCommand({getItem:()=>JSON.stringify({action:'start',key:run,started:Date.now(),input:{request_id:id}})},'receipt'),null);
});
const request=(method,body,origin='http://127.0.0.1:3000')=>new Request(`http://127.0.0.1:3000/api/v1/projects/${id}/runs`,{method,headers:{Origin:origin,'Content-Type':'application/json','Idempotency-Key':run,Authorization:'Bearer forged','X-User-ID':'forged'},...(body?{body:JSON.stringify(body)}:{})});
test('run commands use generated fixed routes, private identity and separate stable keys',async () => {
 const body={request_id:id,expected_brain_revision_id:run};
 const response=await handleRunRequest(request('POST',body),id,'runs',env,undefined,async (req,init)=>{
  assert.equal(req.url,`http://127.0.0.1:8000/v1/projects/${id}/runs`);assert.deepEqual(await req.json(),body);
  assert.equal(req.headers.get('Authorization'),`Bearer ${token}`); assert.equal(req.headers.get('X-User-ID'),null);assert.equal(req.headers.get('Idempotency-Key'),run);assert.equal(init.redirect,'error');
  return Response.json({id:run},{status:202});
 });assert.equal(response.status,202);
 for (const action of ['retry','cancel']) {
  const result=await handleRunRequest(request('POST',{}),id,action,env,run,async req=>{assert.equal(req.url,`http://127.0.0.1:8000/v1/projects/${id}/runs/${run}/${action}`);assert.deepEqual(await req.json(),{});return Response.json({id:run});});assert.equal(result.status,200);
 }
});
test('run gateway rejects fixture flags, cross-origin commands, methods and invalid frozen input',async () => {
 let calls=0;const send=async()=>{calls++;return Response.json({});};const body={request_id:id,expected_brain_revision_id:run};
 for(const [req,resource,status] of [[request('POST',{...body,scenario:'terminal-failure'}),'runs',422],[request('POST',body,'https://foreign.test'),'runs',403],[request('POST',{}),'run',405],[request('POST',{request_id:id}),'runs',422],[request('POST',{execute:true}),'retry',422]])assert.equal((await handleRunRequest(req,id,resource,env,run,send)).status,status);
 assert.equal(calls,0);
});
test('SSE gateway preserves header precedence and forwards unbuffered bytes with abort propagation',async () => {
 const controller=new AbortController();const request=new Request(`http://127.0.0.1:3000/api/v1/projects/${id}/events/stream?after_sequence=1`,{headers:{'Last-Event-ID':'7',Authorization:'Bearer forged'},signal:controller.signal});
 let streamController;const body=new ReadableStream({start(c){streamController=c;c.enqueue(new TextEncoder().encode('event: build_event\nid: 8\ndata: {}\n\n'));}});
 const response=await handleEventStream(request,id,env,async (req,init)=>{
  assert.equal(new URL(req.url).searchParams.get('after_sequence'),'7');assert.equal(req.headers.get('last-event-id'),'7');assert.equal(req.headers.get('Authorization'),`Bearer ${token}`);assert.equal(init.cache,'no-store');
  controller.abort();assert.equal(req.signal.aborted,true);return new Response(body,{headers:{'Content-Type':'text/event-stream','Set-Cookie':'secret=1'}});
 });
 assert.equal(response.headers.get('Set-Cookie'),null);assert.equal(response.headers.get('X-Accel-Buffering'),'no');
 const reader=response.body.getReader();assert.match(new TextDecoder().decode((await reader.read()).value),/id: 8/);streamController.close();await reader.cancel();
 const invalid=await handleEventStream(new Request(`http://127.0.0.1:3000?after_sequence=0`,{headers:{'Last-Event-ID':'bad'}}),id,env,async()=>{throw new Error('must not send');});assert.equal(invalid.status,422);
});
