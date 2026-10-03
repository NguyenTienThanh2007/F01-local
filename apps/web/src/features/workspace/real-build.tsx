'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {buildReceipt,type BuildReceipt} from '@/lib/workspace/build-receipt';
import type {components} from '@f01/api-client/schema';
import {projectRequest,ProjectAPIError} from '@/lib/projects/browser';
import {useResource,useWorkspace,ResourceState} from './workspace';
type Builds=components['schemas']['BuildList'];
type Proposals=components['schemas']['ProposalList'];
type Session=components['schemas']['SessionView'];
type Receipt=BuildReceipt;
export function RealBuildPanel(){
 const {id,snapshot,refresh}=useWorkspace();
 const session=useResource<Session>('/session'),plans=useResource<Proposals>(`/projects/${id}/planning/proposals`),builds=useResource<Builds>(`/projects/${id}/builds`);
 const [pending,setPending]=useState(false),[error,setError]=useState(''),[receipt,setReceipt]=useState<Receipt|null>(null);
 const receiptName=`f01:build:${id}`;
 useEffect(()=>{try{setReceipt(buildReceipt(JSON.parse(sessionStorage.getItem(receiptName)??'null'),id));}catch{}},[receiptName,id]);
 useEffect(()=>{if(!snapshot.active_run||snapshot.active_run.mode!=='real')return;const timer=setInterval(()=>{void refresh();builds.retry();},1500);return()=>clearInterval(timer);},[snapshot.active_run?.id,refresh]);
 const current=plans.data?.items.find(p=>p.reviewed&&p.current_context),latest=builds.data?.items[0];
 async function perform(command:Receipt){
  setPending(true);setError('');setReceipt(command);
  try{sessionStorage.setItem(receiptName,JSON.stringify(command));}catch{}
  try{await projectRequest(command.path,{method:'POST',headers:{'Idempotency-Key':command.key},body:JSON.stringify(command.body)});sessionStorage.removeItem(receiptName);setReceipt(null);await refresh();builds.retry();}
  catch(e){setError(e instanceof Error?e.message:'Build command unavailable.');if(e instanceof ProjectAPIError && e.status>=400 && e.status<500 && ![408,425].includes(e.status)){sessionStorage.removeItem(receiptName);setReceipt(null);}}
  finally{setPending(false);}
 }
 if(!session.data?.capabilities?.real_generation&&!latest)return null;
 return <section className="workspace-notice" aria-label="Real build"><span className="meta">REAL EXECUTION / NEXT.JS PREVIEW</span><h3>{latest?`${latest.run.status} · ${latest.phase.replaceAll('_',' ')}`:'Build the reviewed plan'}</h3>
  <p>Generated source passes isolated typecheck, build, tests when present, and runtime health checks. Production deployment is a later stage.</p>
  {error&&<p role="alert">{error}</p>}
  {receipt?<button className="button button-secondary" disabled={pending} onClick={()=>void perform(receipt)}>Resolve saved build command</button>:<>
   {!snapshot.active_run&&session.data?.capabilities?.real_generation&&<button className="button button-primary" disabled={pending||!current||Boolean(snapshot.project.archived_at)} onClick={()=>current&&void perform({key:crypto.randomUUID(),path:`/projects/${id}/builds`,body:{proposal_id:current.id}})}>Build reviewed plan</button>}
   {snapshot.active_run?.mode==='real'&&<button className="button button-secondary" disabled={pending} onClick={()=>void perform({key:crypto.randomUUID(),path:`/projects/${id}/builds/${snapshot.active_run!.id}/cancel`,body:{}})}>Cancel real build</button>}
   {latest?.run.status==='failed'&&!snapshot.active_run&&<button className="button button-secondary" disabled={pending||!current} onClick={()=>void perform({key:crypto.randomUUID(),path:`/projects/${id}/builds/${latest.run.id}/retry`,body:{}})}>Retry real build</button>}
  </>}
  {!current&&<p><Link href={`/projects/${id}/planning`}>Review a current plan</Link> to authorize source generation.</p>}
  <ResourceState {...builds}/>
  {latest&&<details><summary>Source and verification evidence</summary><p>Repair attempts: {latest.repair_attempts} · Run {latest.run.id}</p>{latest.candidates.map(c=><article key={c.id}><p>Candidate {c.attempt}: {c.digest}</p><ul>{c.files.map((f,n)=><li key={n}>{String(f.path)} · {String(f.bytes)} bytes</li>)}</ul></article>)}<ul>{latest.evidence.map((e,n)=><li key={n}>{e.phase} · exit {e.exit_code} · {e.duration_ms} ms{e.diagnostics.map(d=>` · ${d.code}${d.path?` (${d.path}:${d.line??''})`:''}`).join('')}</li>)}</ul></details>}
 </section>;
}
export function SourceInspector(){
 const {id,snapshot}=useWorkspace();const version=snapshot.current_version;
 const source=useResource<components['schemas']['SourceArtifact']>(version?.mode==='real'?`/projects/${id}/versions/${version.id}/source`:null);
 return <section><span className="meta">VERIFIED SOURCE</span><h2>Source files</h2><ResourceState {...source}/>{!source.data&&<p>No verified generated source is available for this version.</p>}{source.data&&<><p>Digest: {source.data.digest}</p>{source.data.files.map(file=><details key={file.path}><summary>{file.path}</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{file.content}</pre></details>)}</>}</section>;
}
