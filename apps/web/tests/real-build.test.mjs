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

// The states below exercise saved contracts. They do not pretend a Docker worker ran.
const {observeBuild,buildPulse,buildReadUnavailable}=await import('../src/lib/workspace/build-progress.ts');
const {projectJourney}=await import('../src/lib/workspace/journey.ts');
const f=await import('./build-observation-fixtures.mjs');
const {observedRun,acknowledgementObserved}=await import('../src/lib/workspace/command-state.ts');
const observed=(detail,extras={})=>observeBuild({run:detail.run,detail,events:[],version:null,now:f.now,...extras});
test('accepted queued command gives immediate activity without completed build checks',()=>{
 const p=observed(f.detail({run:f.run(),phase:'context_resolution'}));assert.equal(p.title,'Build queued');assert.equal(p.animate,true);assert.equal(p.state,'waiting');assert.equal(p.steps[0].state,'complete');assert.match(p.steps[1].description,/Waiting for a worker/);assert.ok(p.steps.slice(2).every(s=>s.state==='pending'));assert.ok(!('percent' in p)&&!('eta' in p));
});
test('generation pending and saved source advance only observed stages',()=>{
 const generating=observed(f.detail());assert.equal(generating.stage,1);assert.equal(generating.steps[1].state,'active');assert.match(generating.description,/Generating application files/);
 const files=observed(f.detail({phase:'generated',candidates:[f.candidate()]}));assert.equal(files.stage,2);assert.equal(files.steps[1].state,'complete');assert.equal(files.steps[2].state,'active');assert.equal(files.steps[3].state,'pending');
});
test('building, verifying, preparing and Ready require candidate checks and atomic publication',()=>{
 const d=f.detail({phase:'install',candidates:[f.candidate()],current_candidate_evidence:f.checks().slice(0,2)});
 assert.equal(observed(d).stage,2);
 d.current_candidate_evidence=f.checks().slice(0,4);d.phase='build';assert.equal(observed(d).stage,3);assert.equal(observed(d).steps[3].state,'active');
 d.current_candidate_evidence=f.checks().slice(0,5);d.phase='test';assert.equal(observed(d).stage,4);assert.equal(observed(d).steps[5].state,'pending');
 d.current_candidate_evidence=f.checks();d.phase='verification';assert.equal(observed(d).published,false);
 d.run=f.run({status:'succeeded'});d.phase='preview_ready';assert.equal(observed(d).published,false,'A completed run alone is not its published preview.');
 const ready=observed(d,{version:f.version()});assert.equal(ready.published,true);assert.ok(ready.steps.every(s=>s.state==='complete'));assert.equal(ready.animate,false);
 assert.equal(observed(d,{version:f.version({run_id:f.ids.brain})}).published,false);assert.equal(observed(d,{version:f.version({project_id:f.ids.brain})}).published,false);
});
test('repair preserves old immutable evidence but resets checks for the new candidate',()=>{
 const older=f.candidate(),newer=f.candidate({id:f.ids.brain,attempt:2});
 const d=f.detail({phase:'generation_pending',repair_attempts:1,candidates:[older],evidence:f.checks(),current_candidate_evidence:f.checks()});
 const repairing=observed(d);assert.equal(repairing.stage,1);assert.match(repairing.description,/Repair attempt 1/);assert.equal(repairing.steps[2].state,'pending');
 d.phase='generated';d.candidates.push(newer);d.current_candidate_evidence=[];const next=observed(d);assert.equal(next.stage,2);assert.equal(next.steps[2].state,'active');assert.equal(next.steps[3].state,'pending');assert.equal(next.steps[5].state,'pending');
 d.current_candidate_evidence=f.checks().slice(0,4);assert.equal(observed(d).stage,3,'Scoped DTO checks restore accurate repair progress without trace backfill.');
});
test('prior candidate and foreign trace events never complete a new attempt',()=>{
 const d=f.detail({phase:'generated',candidates:[f.candidate(),f.candidate({id:f.ids.brain,attempt:2})],evidence:f.checks()});
 const foreign={id:f.ids.release,project_id:f.ids.project,run_id:f.ids.run,mode:'real',sequence:2,severity:'info',occurred_at:f.stamp(0),payload:{candidate_id:f.ids.candidate,evidence_id:f.ids.version,execution_phase:'build'}};
 assert.equal(observed(d,{events:[foreign]}).steps[2].state,'active');
 const legacy={...d};delete legacy.current_candidate_evidence;assert.equal(observed(legacy,{events:[foreign]}).steps[2].state,'active');
 const p=observeBuild({run:f.run({status:'running'}),detail:{...d,run:f.run({id:f.ids.brain,status:'succeeded'})},events:[],version:f.version(),now:f.now});assert.equal(p.published,false);
});
test('quiet stage with a recent heartbeat waits visibly; stale worker and lost connection stop animation',()=>{
 const d=f.detail({run:f.run({status:'running',created_at:f.stamp(-90000),started_at:f.stamp(-85000),last_heartbeat_at:f.stamp(-1000)}),progress_updated_at:f.stamp(-60000)});
 const waiting=observed(d);assert.equal(waiting.state,'waiting');assert.equal(waiting.animate,false);assert.match(waiting.waiting,/next result is still pending/);
 d.run.last_heartbeat_at=f.stamp(-31000);d.repair_attempts=1;const stalled=observed(d);assert.equal(stalled.state,'blocked');assert.equal(stalled.title,'Build needs a status check');assert.equal(stalled.animate,false);assert.match(stalled.waiting,/interrupted worker/);
 d.run.last_heartbeat_at=f.stamp(-1000);d.progress_updated_at=f.stamp(-1000);assert.equal(observed(d).state,'active','Fresh persisted observation survives missing trace history.');
 assert.equal(observed(d,{disconnected:true}).state,'blocked');assert.equal(observed(d,{disconnected:true}).animate,false);
 const queued=observed(f.detail({run:f.run({created_at:f.stamp(-60000)}),progress_updated_at:f.stamp(-60000)}));assert.match(queued.waiting,/no worker has started/);assert.equal(queued.animate,false);
});
test('failed, canceled and cancellation requested remain explicit and never reach Ready',()=>{
 for(const status of ['failed','canceled']){const p=observed(f.detail({run:f.run({status,error_code:'PROVIDER_OUTCOME_UNKNOWN'})}));assert.equal(p.state,status);assert.equal(p.animate,false);assert.equal(p.steps[5].state,'pending');}
 const cancel=observed(f.detail({cancel_requested:true}));assert.equal(cancel.title,'Cancellation requested');assert.equal(cancel.animate,false);assert.match(cancel.description,/confirm cancellation/);
 assert.throws(()=>observeBuild({run:f.run({mode:'simulated'}),detail:null,events:[],version:null,now:f.now}),/real provenance/);
});
test('journey uses Create Plan Build Preview Deploy Live without treating navigation as evidence',()=>{
 const input={snapshot:f.snapshot(),plans:null,releases:null,progress:null,now:f.now};const first=projectJourney({...input,deploySelected:true});assert.equal(first.step,1);assert.deepEqual(first.steps.map(s=>s.label),['Create','Plan','Build','Preview','Deploy','Live']);assert.equal(first.steps[0].state,'complete');assert.equal(first.steps[5].state,'pending');
 const review=projectJourney({...input,plans:{items:[f.proposal()]}});assert.equal(review.step,1);assert.match(review.title,/Review/);
 const approved=projectJourney({...input,plans:{items:[f.proposal({reviewed:true})]}});assert.equal(approved.step,2);assert.equal(approved.steps[1].state,'complete');assert.equal(approved.steps[3].state,'pending');
 const queued=f.detail({run:f.run(),phase:'context_resolution'}),building=projectJourney({...input,snapshot:f.snapshot({active_run:queued.run,latest_run:queued.run}),progress:observed(queued)});assert.equal(building.step,2);assert.equal(building.state,'waiting');
});
test('update journey preserves last confirmed Live while rebuild fails or preview is ahead',()=>{
 const v=f.version(),live=f.release(),r=f.releases({current_release_id:live.id,releases:[live]});
 const failed=f.detail({run:f.run({status:'failed',base_version_id:v.id,created_at:f.stamp(-5000),error_code:'REPAIR_EXHAUSTED'})});
 const input={snapshot:f.snapshot({current_version:v,latest_run:failed.run}),plans:null,releases:r,progress:observed(failed,{version:v}),now:f.now};
 const update=projectJourney(input);assert.equal(update.update,true);assert.equal(update.step,2);assert.equal(update.state,'failed');assert.equal(update.release.id,live.id);assert.equal(update.steps[5].state,'pending');
 const fresh=f.version({id:f.ids.brain,number:2}),success=f.detail({run:f.run({status:'succeeded',base_version_id:v.id}),phase:'preview_ready'});
 const preview=projectJourney({...input,snapshot:f.snapshot({current_version:fresh,latest_run:success.run}),progress:observed(success,{version:fresh})});assert.equal(preview.step,3);assert.equal(preview.update,true);assert.equal(preview.steps[2].state,'complete');assert.equal(preview.steps[4].state,'pending');
 const publishing=projectJourney({...input,releases:f.releases({current_release_id:live.id,releases:[f.release({id:f.ids.brain,state:'staging'}),live]})});assert.equal(publishing.step,4);assert.equal(publishing.steps[5].state,'pending');
});
test('only the confirmed current release reaches Live; expired preview and session are blocked',()=>{
 const v=f.version(),live=f.release(),input={snapshot:f.snapshot({current_version:v}),plans:null,releases:f.releases({current_release_id:live.id,releases:[live]}),progress:null,now:f.now};
 const ready=projectJourney(input);assert.equal(ready.step,5);assert.equal(ready.state,'complete');assert.ok(ready.steps.every(s=>s.state==='complete'));
 const blocked=projectJourney({...input,blocked:true});assert.equal(blocked.state,'blocked');
 const expired=projectJourney({...input,releases:null,snapshot:f.snapshot({current_version:f.version({preview_descriptor:{...v.preview_descriptor,expires_at:f.stamp(-1)}})})});assert.equal(expired.step,3);assert.equal(expired.state,'blocked');assert.equal(expired.steps[5].state,'pending');
});

test('demonstration and foreign release records cannot masquerade as Live',()=>{
 const live=f.release(),input={snapshot:f.snapshot({current_version:f.version({mode:'simulated',preview_descriptor:{kind:'fixture',fixture_id:'crm-v1'}})}),plans:null,releases:f.releases({current_release_id:live.id,releases:[live]}),progress:null,now:f.now,deploySelected:true};
 const demo=projectJourney(input);assert.equal(demo.currentLive,false);assert.equal(demo.step,3);assert.equal(demo.steps[5].state,'pending');
 const foreign=projectJourney({...input,snapshot:f.snapshot({current_version:f.version()}),releases:f.releases({current_release_id:live.id,releases:[{...live,project_id:f.ids.brain}]})});assert.equal(foreign.currentLive,false);
});
test('newer repair trace invalidates completed checks before the detail poll catches up',()=>{
 const d=f.detail({phase:'test',candidates:[f.candidate()],current_candidate_evidence:f.checks().slice(0,5),progress_sequence:1});
 const event={id:f.ids.release,project_id:f.ids.project,run_id:f.ids.run,mode:'real',sequence:2,severity:'info',occurred_at:f.stamp(-1000),payload:{execution_phase:'repair_attempt',resolves_issue_id:f.ids.candidate+':test'}};
 const p=observed(d,{events:[event]});assert.equal(p.stage,1);assert.equal(p.steps[2].state,'pending');assert.match(p.description,/repair/i);
});
test('a newer generated candidate cannot inherit prior checks during read/stream races',()=>{
 const d=f.detail({phase:'test',candidates:[f.candidate()],current_candidate_evidence:f.checks().slice(0,5),progress_sequence:1});
 const event={id:f.ids.release,project_id:f.ids.project,run_id:f.ids.run,mode:'real',sequence:2,severity:'info',occurred_at:f.stamp(-1000),payload:{execution_phase:'generated',candidate_id:f.ids.brain}};
 const p=observed(d,{events:[event]});assert.equal(p.stage,2);assert.equal(p.steps[2].state,'active');assert.equal(p.steps[3].state,'pending');
});
test('new-candidate check events cannot inherit old checks while the detail read is stale',()=>{
 const d=f.detail({phase:'test',candidates:[f.candidate()],current_candidate_evidence:f.checks().slice(0,5),progress_sequence:1});
 const event={id:f.ids.release,project_id:f.ids.project,run_id:f.ids.run,mode:'real',sequence:3,severity:'info',occurred_at:f.stamp(-1000),payload:{execution_phase:'materialization',candidate_id:f.ids.brain,evidence_id:f.ids.version}};
 const p=observed(d,{events:[event]});assert.equal(p.stage,2);assert.equal(p.steps[3].state,'pending');
});
test('saved generated events advance a stale generation-pending read without inventing checks',()=>{
 const d=f.detail({progress_sequence:1});
 const event={id:f.ids.release,project_id:f.ids.project,run_id:f.ids.run,mode:'real',sequence:2,severity:'info',occurred_at:f.stamp(-1000),payload:{execution_phase:'generated',candidate_id:f.ids.brain}};
 const p=observed(d,{events:[event]});assert.equal(p.stage,2);assert.equal(p.steps[2].state,'active');assert.equal(p.steps[3].state,'pending');
});
test('context resolution does not claim the generation request has started',()=>{
 const p=observed(f.detail({phase:'context_resolution'}));assert.equal(p.stage,0);assert.match(p.description,/before generation/);assert.equal(p.steps[1].state,'pending');
});
test('missing detail preserves blocked connectivity and newer terminal state',()=>{
 const running=f.run({status:'running',started_at:f.stamp(-3000),last_heartbeat_at:f.stamp(-1000)});
 const offline=observeBuild({run:running,detail:null,events:[],version:null,now:f.now,disconnected:true});assert.equal(offline.state,'blocked');assert.equal(offline.animate,false);
 const canceled=observeBuild({run:{...running,status:'canceled',finished_at:f.stamp(0)},detail:f.detail(),events:[],version:null,now:f.now});assert.equal(canceled.run.status,'canceled');assert.equal(canceled.animate,false);
});
test('approved plans with unavailable runtime show a blocked Build and a recovery action',()=>{
 const j=projectJourney({snapshot:f.snapshot(),plans:{items:[f.proposal({reviewed:true})]},releases:null,progress:null,runtimeAvailable:false,now:f.now});assert.equal(j.step,2);assert.equal(j.state,'blocked');assert.match(j.next,/Settings/);assert.equal(j.steps[3].state,'pending');
});
test('publishing preparation, reconciliation, failures and cancellation retain observed states',()=>{
 const v=f.version(),input={snapshot:f.snapshot({current_version:v}),plans:null,progress:null,now:f.now,deploySelected:true};
 const packaging=projectJourney({...input,releases:f.releases({preparations:[{version_id:v.id,state:'packaging'}]})});assert.equal(packaging.step,4);assert.equal(packaging.state,'active');assert.equal(packaging.steps[5].state,'pending');
 const reconciling=projectJourney({...input,releases:f.releases({releases:[f.release({state:'reconciling'})]})});assert.equal(reconciling.state,'waiting');assert.equal(reconciling.currentLive,false);
 const failed=projectJourney({...input,releases:f.releases({releases:[f.release({state:'failed'})]})});assert.equal(failed.state,'failed');assert.match(failed.next,/same reviewed package/);
 const canceled=projectJourney({...input,releases:f.releases({releases:[f.release({state:'canceled'})]})});assert.equal(canceled.state,'canceled');assert.match(canceled.title,/canceled/);
 const hosting=projectJourney({...input,releases:f.releases({hosting_setup:{state:'failed'}})});assert.equal(hosting.state,'failed');assert.match(hosting.next,/hosting error/);
});
test('a failed replacement release keeps its own attention journey beside last confirmed Live',()=>{
 const v=f.version(),live=f.release(),replacement=f.release({id:f.ids.brain,state:'failed',created_at:f.stamp(-1000)});
 const input={snapshot:f.snapshot({current_version:v}),plans:null,progress:null,now:f.now,releases:f.releases({current_release_id:live.id,releases:[replacement,live]})};
 const failed=projectJourney(input);assert.equal(failed.currentLive,true);assert.equal(failed.update,true);assert.equal(failed.step,4);assert.equal(failed.state,'failed');assert.equal(failed.release.id,live.id);assert.equal(failed.steps[5].state,'pending');
 const active=projectJourney({...input,releases:f.releases({current_release_id:live.id,releases:[{...replacement,state:'reconciling'},live]})});assert.equal(active.update,true);assert.equal(active.step,4);assert.equal(active.state,'waiting');
});
test('worker recovery invalidates old checks before the detail poll catches up',()=>{
 const d=f.detail({phase:'test',candidates:[f.candidate()],current_candidate_evidence:f.checks().slice(0,5),progress_sequence:1});
 const event={id:f.ids.release,project_id:f.ids.project,run_id:f.ids.run,mode:'real',sequence:2,severity:'info',occurred_at:f.stamp(-1000),payload:{execution_phase:'restart_recovery'}};
 const p=observed(d,{events:[event]});assert.equal(p.stage,2);assert.equal(p.steps[3].state,'pending');assert.match(p.description,/rerun verification/);
});
test('confirmed cancellation stays visible until a stale running snapshot catches up',()=>{
 const running=f.run({status:'running'}),canceled={...running,status:'canceled',finished_at:f.stamp(0)},snapshot=f.snapshot({active_run:running,latest_run:running});
 assert.equal(acknowledgementObserved(snapshot,canceled),false);assert.equal(observedRun(snapshot,canceled).status,'canceled');
 assert.equal(acknowledgementObserved({...snapshot,active_run:null,latest_run:canceled},canceled),true);assert.equal(observedRun({...snapshot,active_run:null,latest_run:canceled},canceled).status,'canceled');
});
test('an accepted new build is visible ahead of an older snapshot and later reads advance it',()=>{
 const previous=f.run({status:'running'}),queued=f.run({id:f.ids.brain}),snapshot=f.snapshot({active_run:previous,latest_run:previous});
 assert.equal(observedRun(snapshot,queued).id,queued.id);
 const started={...queued,status:'running'};assert.equal(observedRun({...snapshot,active_run:started,latest_run:started},queued).status,'running');
});
test('workspace activity never keeps animating a confirmed terminal build or a waiting observation',()=>{
 for(const status of ['failed','canceled']){const p=observed(f.detail({run:f.run({status})}));assert.ok(['error','idle'].includes(buildPulse(p).state));assert.equal(buildPulse(p).label,p.title);}
 const waiting=observed(f.detail(),{disconnected:true});assert.equal(buildPulse(waiting).state,'idle');
 const succeeded=observed(f.detail({run:f.run({status:'succeeded'}),phase:'preview_ready'}));assert.equal(buildPulse(succeeded).state,'idle');
 assert.equal(buildPulse(observed(f.detail({run:f.run({status:'succeeded'}),phase:'preview_ready'}),{version:f.version()})),null);
});
test('saved build reads remain authoritative when only the event connection is interrupted',()=>{
 const read={currentRead:true,readError:false,historyError:true,transport:'offline'};
 assert.equal(buildReadUnavailable(read),false);
 assert.equal(buildReadUnavailable({...read,readError:true}),true);
 assert.equal(buildReadUnavailable({...read,currentRead:false}),true);
 for(const transport of ['session expired','access unavailable'])assert.equal(buildReadUnavailable({...read,transport}),true);
});
