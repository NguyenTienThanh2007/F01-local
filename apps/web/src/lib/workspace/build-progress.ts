import type {components} from '@f01/api-client/schema';
import type {BuildEvent} from './trace.ts';
import type {Run,Version} from './contracts.ts';
export type BuildDetail=components['schemas']['BuildDetail'];
export type ObservedState='complete'|'active'|'waiting'|'pending'|'failed'|'canceled'|'blocked';
export const buildStages=['Understanding','Generating code','Building','Verifying','Preparing preview','Ready'] as const;
export type BuildProgress={run:Run;stage:number;state:ObservedState;title:string;description:string;steps:{label:string;state:ObservedState;description:string}[];animate:boolean;waiting:string|null;lastObservedAt:string;lastHeartbeatAt:string|null;repairing:boolean;published:boolean};
// These thresholds describe missing observations, never a build duration or ETA.
export const PROGRESS_WAIT_MS=45000,HEARTBEAT_WAIT_MS=30000;
export function buildReadUnavailable({currentRead,readError,historyError,transport}:{currentRead:boolean;readError:boolean;historyError:boolean;transport:string}){
 return readError||!currentRead&&historyError||['session expired','access unavailable'].includes(transport)||transport==='offline'&&!currentRead;
}
export function buildPulse(progress:BuildProgress){
 if(['failed','canceled'].includes(progress.run.status))return {state:progress.run.status==='failed'?'error' as const:'idle' as const,label:progress.title};
 if(progress.run.status==='succeeded')return progress.published?null:{state:'idle' as const,label:progress.title};
 return {state:progress.animate?progress.stage>=3?'verifying' as const:'building' as const:'idle' as const,label:progress.state==='active'?progress.steps[progress.stage]!.label:progress.title};
}
const age=(now:number,value:string|null|undefined)=>value&&Number.isFinite(Date.parse(value))?Math.max(0,now-Date.parse(value)):null;
export function observeBuild({run,detail,events,version,now,disconnected=false}:{run:Run;detail:BuildDetail|null;events:BuildEvent[];version:Version|null;now:number;disconnected?:boolean}):BuildProgress{
 if(run.mode!=='real')throw Error('Real build observation requires real provenance.');
 const record=detail?.run.id===run.id&&detail.run.project_id===run.project_id&&detail.run.mode==='real'?detail:null;
 // Never attach an older build's phase/evidence to an accepted new command.
 const terminal=(status:Run['status'])=>['succeeded','failed','canceled'].includes(status);
 const saved=record&&!terminal(run.status)?record.run:run;
 const trace=events.filter(event=>event.mode==='real'&&event.run_id===saved.id&&event.project_id===saved.project_id).sort((a,b)=>a.sequence-b.sequence);
 const candidate=record?.candidates.at(-1);
 const progressPhases=['context_resolution','generation','repair_attempt','generated','materialization','install','typecheck','build','test','verification','recovery','restart_recovery','preview_ready','issue_detection'];
 const lastTrace=trace.filter(event=>progressPhases.includes(event.payload.execution_phase??'')).at(-1),newerTrace=Boolean(lastTrace&&lastTrace.sequence>(record?.progress_sequence??0));
 const tracePhase=newerTrace?lastTrace?.payload.execution_phase:null;
 const phase=tracePhase==='restart_recovery'?'recovery':tracePhase??record?.phase;
 const generationPending=phase==='generation_pending'||phase==='generation'||phase==='repair_attempt';
 const newerCandidate=trace.filter(event=>event.sequence>(record?.progress_sequence??0)&&event.payload.candidate_id).at(-1)?.payload.candidate_id;
 const candidateId=newerCandidate??candidate?.id;
 const candidateKnown=Boolean(candidate&&candidate.id===candidateId);
 let repairing=Boolean(record?.repair_attempts&&generationPending)||tracePhase==='repair_attempt';
 const candidateEvents=trace.filter(event=>event.payload.candidate_id===candidateId&&event.payload.evidence_id);
 const passed=new Set<string>(),failed=new Set<string>();
 if(candidateId&&!generationPending&&!['recovery','context_resolution'].includes(phase??'')){
  if(candidateKnown&&(record?.current_candidate_evidence!==undefined||record?.candidates.length===1)){for(const evidence of record.current_candidate_evidence??record.evidence){(evidence.exit_code===0?passed:failed).add(evidence.phase);}}
  // Events retain candidate identity across repair; the flat evidence list does not.
  for(const event of candidateEvents){const phase=event.payload.execution_phase;if(phase)(event.severity==='error'?failed:passed).add(phase);}
 }
 const checkFailed=failed.size>0&&!generationPending;
 repairing=repairing||Boolean(checkFailed&&saved.status==='running');
 const hasTests=Boolean(candidate?.files.some(file=>typeof file.path==='string'&&file.path.startsWith('tests/')));
 const generated=Boolean(candidateId&&!generationPending);
 const built=generated&&['materialization','install','typecheck','build'].every(phase=>passed.has(phase)&&!failed.has(phase));
 const checked=built&&candidateKnown&&(!hasTests||passed.has('test')&&!failed.has('test'));
 const previewChecked=checked&&passed.has('verification')&&!failed.has('verification');
 const published=saved.status==='succeeded'&&record?.phase==='preview_ready'&&version?.mode==='real'&&version.run_id===saved.id&&version.project_id===saved.project_id;
 // Publication is an atomic server guarantee of the required current-candidate checks.
 const complete=[Boolean(saved.input_brain_revision_id&&saved.request_id),generated,built,checked,previewChecked,published];
 if(published)complete.fill(true);
 let stage=published?5:previewChecked?4:checked?4:built?3:generated?2:phase==='context_resolution'&&saved.status==='running'?0:1;
 let state:ObservedState=saved.status==='queued'?'waiting':saved.status==='failed'?'failed':saved.status==='canceled'?'canceled':published?'complete':'active';
 if(saved.status==='succeeded'&&!published){state='waiting';stage=4;}
 if(record?.cancel_requested&&['queued','running'].includes(saved.status))state='waiting';
 if(!record&&saved.status==='running')state='waiting';
 if(checkFailed&&saved.status==='running')state='waiting';
 const lastEvent=trace.at(-1);
 const timestamps=[record?.progress_updated_at,lastEvent?.occurred_at,candidate?.created_at,saved.started_at,saved.created_at].filter((value):value is string=>typeof value==='string'&&Number.isFinite(Date.parse(value)));
 const lastObservedAt=timestamps.sort((a,b)=>Date.parse(b)-Date.parse(a))[0]??saved.created_at;
 const noProgress=(age(now,lastObservedAt)??0)>=PROGRESS_WAIT_MS;
 const heartbeatAge=age(now,saved.last_heartbeat_at??saved.started_at);
 let waiting:string|null=null;
 if(disconnected&&['queued','running'].includes(saved.status)){state='blocked';waiting='Connection interrupted. Showing the last saved build state; worker activity cannot be confirmed until the connection returns.';}
 else if(saved.status==='queued'&&noProgress){state='waiting';waiting='This build is saved, but no worker has started it yet. Check saved status or cancel the queued build.';}
 else if(saved.status==='running'&&heartbeatAge!==null&&heartbeatAge>=HEARTBEAT_WAIT_MS){state='blocked';waiting='No recent worker check-in is visible. This may be an interrupted worker. F01 is waiting for saved recovery or a terminal result; you can check status or request cancellation.';}
 else if(saved.status==='running'&&noProgress){state='waiting';waiting='No new build step has been saved recently. The worker has checked in, but the next result is still pending. This does not confirm further progress.';}
 const descriptions=[
  stage===0?'Resolving your saved brief and approved plan before generation begins.':'Your saved brief and approved plan are attached to this build.',
  saved.status==='queued'?'Waiting for a worker before code generation begins.':!record&&!tracePhase?'Waiting to confirm generation from saved build records.':repairing?record?.repair_attempts?`Repair attempt ${record.repair_attempts}: revising application files after a failed check.`:'A repair request is saved. Revising application files after a failed check.':generated?'Application files have been saved.':'Generating application files. Waiting for the generation result.',
  built?'Installation, typecheck and build checks passed.':generated?'Application files are saved. Waiting for the next installation and build result.':'Waiting for application files.',
  checked?hasTests?'Saved typecheck and generated tests passed.':'Saved typecheck passed. This candidate declares no generated tests.':built?'Checking your application. Waiting for the generated test result.':'Waiting for build checks to pass.',
  previewChecked?'Preview health check passed. Waiting for atomic publication.':checked?'Starting and checking the isolated preview.':'Waiting for verification.',
  published?'Verified source and preview were published together.':'Available after verification and preview publication succeed.'
 ];
 let title=published?'Build verified':saved.status==='failed'?'Build needs attention':saved.status==='canceled'?'Build canceled':saved.status==='queued'?'Build queued':repairing?'Repairing your application':state==='blocked'?'Build needs a status check':state==='waiting'?'Waiting for a saved result':'Building your application';
 let description=saved.status==='queued'?'Accepted and saved. Waiting for the build worker to start.':saved.status==='failed'?'This attempt stopped. Your last successful preview and live release stay preserved.':saved.status==='canceled'?'Cancellation is confirmed. Your saved project and last successful versions stay preserved.':saved.status==='succeeded'&&!published?'Build completion is saved. Checking that its verified preview was published.':descriptions[stage]!;
 if(record?.cancel_requested&&['queued','running'].includes(saved.status)){title='Cancellation requested';description='Waiting for the worker to confirm cancellation and cleanup. Your previous preview stays available.';}
 if(checkFailed&&saved.status==='running'){title='A check needs attention';description='A failed check is saved. Waiting for the worker’s repair decision; your last successful versions stay available.';}
 if((phase==='recovery'||phase==='context_resolution'&&candidate)&&saved.status==='running'){title='Recovering your build';description='Saved application files are available. The worker must rerun verification before publishing a preview.';}
 if(!record&&saved.status==='running'&&state!=='blocked'){title='Checking saved build progress';description='This build is recorded as running. Loading its saved stage and check records.';state='waiting';}
 const knownPhase=!record||['context_resolution','generation_pending','generated','materialization','install','typecheck','build','test','verification','preview_ready','recovery'].includes(record.phase);
 if(!knownPhase&&saved.status==='running'){state='blocked';title='Build state needs inspection';description='An unrecognized saved stage needs inspection before further progress can be confirmed.';waiting=description;}
 if(waiting&&knownPhase&&saved.status==='running'){title=state==='blocked'?'Build needs a status check':'Waiting for a saved result';description=waiting;}
 const steps=buildStages.map((label,index)=>({label,state:(index===stage?checkFailed&&saved.status==='running'?'failed':state:complete[index]?'complete':'pending') as ObservedState,description:descriptions[index]!}));
 return {run:saved,stage,state,title,description,steps,animate:['queued','running'].includes(saved.status)&&!waiting&&!record?.cancel_requested&&!checkFailed&&Boolean(record||saved.status==='queued'),waiting,lastObservedAt,lastHeartbeatAt:saved.last_heartbeat_at,repairing,published};
}
