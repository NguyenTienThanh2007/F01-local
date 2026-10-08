'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {buildReceipt,buildReceiptExpired,type BuildReceipt} from '@/lib/workspace/build-receipt';
import {readReceipt,saveReceipt} from '@/lib/workspace/receipt-storage';
import {outcomeIsUnknown} from '@/lib/projects/creation';
import {uuid,type Run} from '@/lib/workspace/contracts';
import type {components} from '@f01/api-client/schema';
import {projectRequest,ProjectAPIError} from '@/lib/projects/browser';
import {useResource,useWorkspace,ResourceState} from './workspace';
import {useFlow,useBuildProgress} from './flow';
import {BuildActivity,BuildTimeline} from './build-progress';

export function RealBuildPanel({onReadyChange,onAttentionChange}:{onReadyChange?:(ready:boolean)=>void;onAttentionChange?:(attention:boolean)=>void}={}){
 const {id,snapshot,refresh,transport}=useWorkspace();
 const {session,plans,builds,build,currentRun,acknowledge}=useFlow();
 const [pending,setPending]=useState(false),[error,setError]=useState(''),[receipt,setReceipt]=useState<BuildReceipt|null>(null),[ready,setReady]=useState(false);
 const busy=useRef(false),receiptName=`f01:build:${id}`;
 useEffect(()=>{setReceipt(readReceipt(receiptName,value=>buildReceipt(value,id)));setReady(true);},[receiptName,id]);
 const active=currentRun&&['queued','running'].includes(currentRun.status)?currentRun:null;
 const accessBlocked=['session expired','access unavailable'].includes(transport);
 const knownRun=currentRun;
 const current=plans.data?.items.find(p=>p.reviewed&&p.current_context&&p.brain_revision_id===snapshot.project.current_brain_revision_id&&p.version_id===snapshot.project.current_version_id),latest=build.data?.run.id===knownRun?.id?build.data:builds.data?.items.find(item=>item.run.id===knownRun?.id);
 const progress=useBuildProgress(knownRun);
 const buildReady=Boolean(current&&!active&&!receipt&&session.data?.capabilities?.real_generation);
 useEffect(()=>{onReadyChange?.(buildReady);},[buildReady,onReadyChange]);
 useEffect(()=>{onAttentionChange?.(Boolean(receipt||error||['failed','canceled'].includes(knownRun?.status??'')));},[Boolean(receipt),error,knownRun?.status,onAttentionChange]);
 const expired=receipt&&buildReceiptExpired(receipt);
 async function perform(command:BuildReceipt){
  if(busy.current||!ready||buildReceiptExpired(command))return;
  busy.current=true;setPending(true);setError('');setReceipt(command);saveReceipt(receiptName,command);
  try{
   const result=await projectRequest<Run>(command.path,{method:'POST',headers:{'Idempotency-Key':command.key},body:JSON.stringify(command.body)});
   if(!result||!uuid.test(result.id)||result.project_id!==id||result.mode!=='real'||!['queued','running','succeeded','failed','canceled'].includes(result.status))throw new ProjectAPIError('SERVICE_UNAVAILABLE',0);
   // A confirmed command stays confirmed even if storage or the following read fails.
   saveReceipt(receiptName,null);setReceipt(null);acknowledge(result);
   await refresh();build.retry();builds.retry();
  }catch(e){
   setError(e instanceof Error?e.message:'Build command unavailable.');
   if(e instanceof ProjectAPIError&&!outcomeIsUnknown(e.status,e.code)&&e.code!=='IDEMPOTENCY_KEY_REUSED'){saveReceipt(receiptName,null);setReceipt(null);}
  }finally{busy.current=false;setPending(false);}
 }
 function command(path:string,body:BuildReceipt['body']):BuildReceipt{return {key:crypto.randomUUID(),path,body,created:Date.now()};}
 if(currentRun?.mode==='simulated')return null;
 if((!session.data?.capabilities?.real_generation||session.data?.capabilities?.execution_mode!=='real')&&!latest&&!receipt&&!active)return <><ResourceState {...session}/>{session.data?.capabilities?.execution_mode==='real'&&<section className="workspace-notice"><h3>Build runtime unavailable</h3><p>Your project and plans are saved. The trusted build runtime must be configured and verified before a build can start.</p><Link className="button button-primary" href={`/projects/${id}/settings`}>Review runtime settings</Link></section>}</>;
 const status=progress?.run.status??active?.status??latest?.run.status;
 const title=pending?'Sending build command…':receipt?'Confirming your saved build':status==='queued'?'Build queued':status==='running'?'Building your application':buildReady?snapshot.current_version?'Ready for the next build':'Ready to build':status==='succeeded'?'Build verified':status==='failed'?'Build needs attention':status==='canceled'?'Build canceled':'Make your first plan';
 return <section className="workspace-notice build-command" data-state={buildReady?'ready':status??'idle'} aria-label="Real build">
  {progress&&(!buildReady||active||['failed','canceled'].includes(status??''))&&(!receipt||active)&&!pending?<><BuildActivity progress={progress}/><BuildTimeline progress={progress}/></>:<><span className="meta">BUILD & VERIFY</span><h3 aria-live="polite">{title}</h3><p>{pending?'Waiting for the server to confirm this command.':receipt?'The command result is unconfirmed. Resolve it with the original saved key and input.':buildReady?'Your approved direction is ready. Start a build from this saved project context.':'Start with the brief you saved. Make a plan and approve it before a build starts.'}</p></>}
  {active?.mode==='real'&&!accessBlocked&&!receipt&&<div className="build-live-actions">{progress?.waiting?<button className="button button-primary" disabled={pending} onClick={()=>{void refresh();build.retry();}}>Check saved build status</button>:<Link className="button button-primary" href={`/projects/${id}?panel=trace`}>Follow Build Trace</Link>}<p>Preview appears automatically after verification and publication succeed.</p></div>}
  {status==='failed'&&latest&&<div className="build-failure" role="alert"><strong>{buildFailure(latest.run.error_code)}</strong><p>Retry uses the failed attempt’s saved plan and context. Planning a change creates a separate direction.</p></div>}
  {error&&<p role="alert">{error}</p>}
  {receipt?<>{expired?<><p role="alert">This command is outside its safe recovery window. Inspect saved build history before starting another build.</p><Link className="button button-primary" href={`/projects/${id}?panel=run`}>Inspect saved build history</Link></>:<button className="button button-primary" disabled={pending||!ready||accessBlocked} onClick={()=>void perform(receipt)}>Resolve saved build command</button>}</>:<>
   {!active&&!accessBlocked&&session.data?.capabilities?.real_generation&&(knownRun?.status==='failed'&&!latest?<button className="button button-primary" disabled={build.pending} onClick={()=>build.retry()}>Check saved build status</button>:latest?.run.status==='failed'?current?<button className="button button-primary" disabled={pending||!ready||Boolean(snapshot.project.archived_at)} onClick={()=>void perform(command(`/projects/${id}/builds/${latest.run.id}/retry`,{}))}>Retry real build</button>:<Link className="button button-primary" href={`/projects/${id}/planning`}>Review a new plan</Link>:current?<button className="button button-primary" disabled={pending||!ready||Boolean(snapshot.project.archived_at)} onClick={()=>void perform(command(`/projects/${id}/builds`,{proposal_id:current.id}))}>Build reviewed plan</button>:status==='succeeded'&&snapshot.current_version?.run_id===latest?.run.id?<Link className="button button-secondary" href={`/projects/${id}`}>Review preview</Link>:<Link className="button button-primary" href={`/projects/${id}/planning`}>Create a plan</Link>)}
   {active?.mode==='real'&&<button className="button button-secondary" disabled={pending||!ready||accessBlocked} onClick={()=>void perform(command(`/projects/${id}/builds/${active.id}/cancel`,{}))}>Cancel real build</button>}
  </>}
  <ResourceState {...plans}/><ResourceState {...build} pending={Boolean(active)&&!build.data&&build.pending}/>
  {latest&&<details><summary>Build details and verification evidence</summary><p>Stage: {latest.phase.replaceAll('_',' ')} · Repair attempts: {latest.repair_attempts} · Run {latest.run.id}</p>{latest.candidates.map(c=><article key={c.id}><p>Candidate {c.attempt}: {c.digest}</p><ul>{c.files.map((f,n)=><li key={n}>{String(f.path)} · {String(f.bytes)} bytes</li>)}</ul></article>)}<ul>{latest.evidence.map((e,n)=><li key={n}>{e.phase} · exit {e.exit_code} · {e.duration_ms} ms{e.diagnostics.map(d=>` · ${d.code}${d.path?` (${d.path}:${d.line??''})`:''}`).join('')}</li>)}</ul></details>}
 </section>;
}
function buildFailure(code:string|null){
 if(code==='SOURCE_PROPOSAL_REJECTED')return 'The proposed source failed the required source-integrity checks. No new candidate or preview was published. Review the saved attempt before retrying.';
 const messages:Record<string,string>={PROVIDER_OUTCOME_UNKNOWN:'The worker stopped while generation was pending. Its provider result is unconfirmed.',BUILD_TIMEOUT:'This build reached its server time limit.',REPAIR_EXHAUSTED:'The saved checks still failed after the allowed repair attempts.',PROVIDER_AUTHENTICATION_FAILED:'The generation provider rejected its configured credentials.',PROVIDER_QUOTA_EXCEEDED:'The generation provider has no remaining allowance.',PROVIDER_TIMEOUT:'The generation provider did not return a result before its deadline.',SOURCE_BUDGET_EXCEEDED:'This attempt reached its configured source-generation allowance.',SOURCE_SECRET_REJECTED:'A security check rejected source or context containing a forbidden credential.',EXECUTION_UNAVAILABLE:'The trusted build runtime is unavailable.'};
 return messages[code??'']??'This attempt did not pass the required checks. Inspect its saved evidence before retrying.';
}
export function SourceInspector(){
 const {id,snapshot}=useWorkspace();const version=snapshot.current_version;
 const source=useResource<components['schemas']['SourceArtifact']>(version?.mode==='real'?`/projects/${id}/versions/${version.id}/source`:null);
 return <section><span className="meta">VERIFIED SOURCE</span><h2>Source files</h2><ResourceState {...source}/>{!source.data&&<p>No verified generated source is available for this version.</p>}{source.data&&<><p>Digest: {source.data.digest}</p>{source.data.files.map(file=><details key={file.path}><summary>{file.path}</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{file.content}</pre></details>)}</>}</section>;
}
