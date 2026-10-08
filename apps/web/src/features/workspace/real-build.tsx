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
type Builds=components['schemas']['BuildList'];
type Proposals=components['schemas']['ProposalList'];
type Session=components['schemas']['SessionView'];

export function RealBuildPanel(){
 const {id,snapshot,refresh}=useWorkspace();
 const session=useResource<Session>('/session'),plans=useResource<Proposals>(`/projects/${id}/planning/proposals`),builds=useResource<Builds>(`/projects/${id}/builds`);
 const [pending,setPending]=useState(false),[error,setError]=useState(''),[receipt,setReceipt]=useState<BuildReceipt|null>(null),[ready,setReady]=useState(false),[confirmed,setConfirmed]=useState<Run|null>(null);
 const busy=useRef(false),receiptName=`f01:build:${id}`;
 useEffect(()=>{setReceipt(readReceipt(receiptName,value=>buildReceipt(value,id)));setReady(true);},[receiptName,id]);
 const active=snapshot.active_run??(confirmed?.status==='queued'||confirmed?.status==='running'?confirmed:null);
 useEffect(()=>{if(snapshot.latest_run?.id===confirmed?.id)setConfirmed(null);},[snapshot.latest_run?.id,snapshot.latest_run?.status,confirmed?.id]);
 useEffect(()=>{
  if(active?.mode!=='real')return;
  let checking=false;
  const timer=setInterval(()=>{if(checking)return;checking=true;void refresh(true,false).finally(()=>{checking=false;});},1500);
  return()=>clearInterval(timer);
 },[active?.id,refresh]);
 useEffect(()=>{builds.retry();},[snapshot.last_sequence]);
 const current=plans.data?.items.find(p=>p.reviewed&&p.current_context&&p.brain_revision_id===snapshot.project.current_brain_revision_id&&p.version_id===snapshot.project.current_version_id),latest=builds.data?.items[0];
 const expired=receipt&&buildReceiptExpired(receipt);
 async function perform(command:BuildReceipt){
  if(busy.current||!ready||buildReceiptExpired(command))return;
  busy.current=true;setPending(true);setError('');setReceipt(command);saveReceipt(receiptName,command);
  try{
   const result=await projectRequest<Run>(command.path,{method:'POST',headers:{'Idempotency-Key':command.key},body:JSON.stringify(command.body)});
   if(!result||!uuid.test(result.id)||result.project_id!==id||result.mode!=='real'||!['queued','running','succeeded','failed','canceled'].includes(result.status))throw new ProjectAPIError('SERVICE_UNAVAILABLE',0);
   // A confirmed command stays confirmed even if storage or the following read fails.
   saveReceipt(receiptName,null);setReceipt(null);setConfirmed(result);
   await refresh();builds.retry();
  }catch(e){
   setError(e instanceof Error?e.message:'Build command unavailable.');
   if(e instanceof ProjectAPIError&&!outcomeIsUnknown(e.status,e.code)&&e.code!=='IDEMPOTENCY_KEY_REUSED'){saveReceipt(receiptName,null);setReceipt(null);}
  }finally{busy.current=false;setPending(false);}
 }
 function command(path:string,body:BuildReceipt['body']):BuildReceipt{return {key:crypto.randomUUID(),path,body,created:Date.now()};}
 if((!session.data?.capabilities?.real_generation||session.data?.capabilities?.execution_mode!=='real')&&!latest&&!receipt)return <><ResourceState {...session}/>{session.data?.capabilities?.execution_mode==='real'&&<section className="workspace-notice"><h3>Build runtime unavailable</h3><p>Your project and plans are saved. The trusted build runtime must be configured and verified before a build can start.</p><Link className="button button-primary" href={`/projects/${id}/planning`}>Review a plan</Link></section>}</>;
 const status=active?.status??latest?.run.status;
 const title=pending?'Sending build command…':receipt?'Confirming your saved build':status==='queued'?'Build queued':status==='running'?'Building your application':status==='succeeded'?'Build verified':status==='failed'?'Build needs attention':status==='canceled'?'Build canceled':'Build your application';
 return <section className="workspace-notice build-command" data-state={status??'idle'} aria-label="Real build">
  <span className="meta">01 / BUILD</span><h3 aria-live="polite">{title}</h3>
  <p>{status==='queued'?'Saved and waiting for the build worker. You can leave and return.':status==='running'?'Generating and checking your application. Build Trace follows each observed step.':status==='succeeded'?'Your verified source and preview are saved.':status==='failed'?'This attempt needs attention. Your last successful version stays available.':status==='canceled'?'This attempt was canceled. Your saved context stays available.':'Turn your reviewed plan into an application in the trusted build environment.'}</p>
  {active?.mode==='real'&&<Link className="button button-primary" href={`/projects/${id}?panel=trace`}>Follow Build Trace</Link>}
  {error&&<p role="alert">{error}</p>}
  {receipt?<>{expired?<p role="alert">This command is outside its safe recovery window. Inspect saved build history before starting another build.</p>:<button className="button button-secondary" disabled={pending||!ready} onClick={()=>void perform(receipt)}>Resolve saved build command</button>}</>:<>
   {!active&&session.data?.capabilities?.real_generation&&(current?<button className="button button-primary" disabled={pending||!ready||Boolean(snapshot.project.archived_at)} onClick={()=>void perform(command(`/projects/${id}/builds`,{proposal_id:current.id}))}>Build reviewed plan</button>:status==='succeeded'&&snapshot.current_version?.run_id===latest?.run.id?<Link className="text-action" href={`/projects/${id}?panel=trace`}>Inspect Build Trace ↗</Link>:<Link className="button button-primary" href={`/projects/${id}/planning`}>Review a plan</Link>)}
   {active?.mode==='real'&&<button className="button button-secondary" disabled={pending||!ready} onClick={()=>void perform(command(`/projects/${id}/builds/${active.id}/cancel`,{}))}>Cancel real build</button>}
  </>}
  {latest?.run.status==='failed'&&!active&&!receipt&&<details><summary>Recovery options</summary><button className="button button-secondary" disabled={pending||!ready||!current||Boolean(snapshot.project.archived_at)} onClick={()=>void perform(command(`/projects/${id}/builds/${latest.run.id}/retry`,{}))}>Retry real build</button></details>}
  <ResourceState {...plans}/><ResourceState {...builds}/>
  {latest&&<details><summary>Build details and verification evidence</summary><p>Stage: {latest.phase.replaceAll('_',' ')} · Repair attempts: {latest.repair_attempts} · Run {latest.run.id}</p>{latest.candidates.map(c=><article key={c.id}><p>Candidate {c.attempt}: {c.digest}</p><ul>{c.files.map((f,n)=><li key={n}>{String(f.path)} · {String(f.bytes)} bytes</li>)}</ul></article>)}<ul>{latest.evidence.map((e,n)=><li key={n}>{e.phase} · exit {e.exit_code} · {e.duration_ms} ms{e.diagnostics.map(d=>` · ${d.code}${d.path?` (${d.path}:${d.line??''})`:''}`).join('')}</li>)}</ul></details>}
 </section>;
}
export function SourceInspector(){
 const {id,snapshot}=useWorkspace();const version=snapshot.current_version;
 const source=useResource<components['schemas']['SourceArtifact']>(version?.mode==='real'?`/projects/${id}/versions/${version.id}/source`:null);
 return <section><span className="meta">VERIFIED SOURCE</span><h2>Source files</h2><ResourceState {...source}/>{!source.data&&<p>No verified generated source is available for this version.</p>}{source.data&&<><p>Digest: {source.data.digest}</p>{source.data.files.map(file=><details key={file.path}><summary>{file.path}</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{file.content}</pre></details>)}</>}</section>;
}
