'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import type {components} from '@f01/api-client/schema';
import {projectRequest,ProjectAPIError} from '@/lib/projects/browser';
import {planningErrors} from '@/lib/planning/contracts';
import {errorMessage} from '@/lib/projects/contracts';
import {uuid} from '@/lib/workspace/contracts';
import {readReceipt,saveReceipt} from '@/lib/workspace/receipt-storage';
import {useWorkspace,useResource,ResourceState,time} from './workspace';
import {useFlow} from './flow';
type Proposal=components['schemas']['ProposalRecord'];
type Attempt=components['schemas']['AttemptRecord'];
type PlanInput=components['schemas']['PlanInput'];
type Receipt={key:string;requestKey:string;input:PlanInput;intent:string;created:number;attemptId?:string};
function parseReceipt(raw:string|null):Receipt|null{try{const r=JSON.parse(raw??'null') as Receipt;if(r&&uuid.test(r.key)&&uuid.test(r.requestKey)&&['initial','change'].includes(r.input.kind)&&uuid.test(r.input.request_id)&&uuid.test(r.input.base_brain_revision_id)&&(r.input.base_version_id===null||uuid.test(r.input.base_version_id))&&typeof r.intent==='string'&&r.intent.length<=10000&&Number.isFinite(r.created)&&r.created>=0&&Date.now()>=r.created&&(!r.attemptId||uuid.test(r.attemptId)))return r;}catch{}return null;}
function ProposalView({record,onReview,busy,changing}:{record:Proposal;onReview:()=>void;busy:boolean;changing:boolean}){
 const content=record.content;
 return <article className="workspace-record planning-proposal">
  <div className="plan-overview"><span className="meta">{record.current_context?'YOUR PROPOSED PLAN':'EARLIER PLAN'}</span><h2>{content.plan.project_title}</h2><p>{content.plan.product_summary}</p><div className="proposal-review">
   {record.reviewed?<><p role="status">Plan approved. Building has not started.</p>{record.current_context&&<Link className={changing?'button button-secondary':'button button-primary'} href={`/projects/${record.project_id}?step=build`}>Continue to build</Link>}</>:<><p>Check the proposed work below. Approving makes this plan available to build.</p><button className={record.current_context&&!changing?'button button-primary':'button button-secondary'} disabled={busy||!record.current_context} onClick={onReview}>Approve this plan</button></>}
   {!record.current_context&&<p>Saved for reference. Use the current project context for your next plan.</p>}
  </div></div>
  <section className="plan-main-scope"><h3>What we will build</h3><ul>{content.scope.map((value,index)=><li key={index}>{value}</li>)}</ul></section>
  <section><h3>Core features</h3>{content.plan.core_features.map((feature,i)=><div key={i}><h4>{feature.name}</h4><p>{feature.description}</p></div>)}</section>
  <section><h3>What a good result looks like</h3><ul>{content.acceptance_criteria.map((value,index)=><li key={index}>{value}</li>)}</ul></section>
  {Boolean(content.out_of_scope.length)&&<section><h3>Not included in this plan</h3><ul>{content.out_of_scope.map((value,index)=><li key={index}>{value}</li>)}</ul></section>}
  <details className="plan-supporting"><summary>Assumptions, users & milestones</summary><h3>Assumptions to check</h3><ul>{content.assumptions.map((value,i)=><li key={i}>{value}</li>)}</ul><h3>Who it is for</h3><ul>{content.plan.target_users.map((value,i)=><li key={i}>{value}</li>)}</ul><h3>Milestones</h3><ol>{content.plan.implementation_milestones.map((item,i)=><li key={i}><strong>{item.title}</strong><ul>{item.deliverables.map((value,j)=><li key={j}>{value}</li>)}</ul></li>)}</ol></details>
  <details className="plan-supporting"><summary>Technical approach & plan provenance</summary><dl>{Object.entries(content.plan.recommended_stack).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl><p>{record.provider} / {record.model} · {time(record.created_at)}</p><p>This is proposed work. No source generation, build or deployment has run for this plan.</p><dl><dt>Request</dt><dd>{record.request_id}</dd><dt>Base version</dt><dd>{record.version_id??'First version'}</dd></dl><pre className="preserved-text">{JSON.stringify(record.context,null,2)}</pre></details>
 </article>;
}
export function PlanningView(){
 const {id,snapshot,refresh,generation}=useWorkspace(),path=`/projects/${id}/planning`,storage=`f01-context-plan:${id}`;
 const {plans:history}=useFlow();
 const usage=useResource<components['schemas']['UsageView']>('/planning/usage');
 const [intent,setIntent]=useState(''),[receipt,setReceipt]=useState<Receipt|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[attempt,setAttempt]=useState<Attempt|null>(null),[ready,setReady]=useState(false),[editorOpen,setEditorOpen]=useState(true);
 const [bases,setBases]=useState({brain:snapshot.project.current_brain_revision_id,version:snapshot.project.current_version_id});
 const busyRef=useRef(false),pollRef=useRef<AbortController|null>(null);
 const shownProposal=useRef<string|null>(null);
 useEffect(()=>{const proposal=history.data?.items[0];if(proposal&&proposal.id!==shownProposal.current){shownProposal.current=proposal.id;if(proposal.current_context)setEditorOpen(false);}},[history.data?.items]);
 useEffect(()=>{const stored=readReceipt(storage,value=>parseReceipt(JSON.stringify(value)));if(stored){setReceipt(stored);setIntent(stored.intent);setBases({brain:stored.input.base_brain_revision_id,version:stored.input.base_version_id});}setReady(true);return()=>pollRef.current?.abort();},[storage]);
 function save(r:Receipt|null){setReceipt(r);saveReceipt(storage,r);}
 const stale=bases.brain!==snapshot.project.current_brain_revision_id||bases.version!==snapshot.project.current_version_id;
 async function finish(value:Attempt){setAttempt(value);if(value.status==='pending')return false;save(null);if(value.status!=='succeeded')setError(value.error_code&&value.error_code in planningErrors?planningErrors[value.error_code as keyof typeof planningErrors].message:errorMessage(value.error_code??'INTERNAL_ERROR'));await refresh();history.retry();return true;}
 async function run(kind:'initial'|'change'){
  if(busyRef.current||!ready)return;busyRef.current=true;pollRef.current=null;setBusy(true);setError('');setAttempt(null);
  let r=receipt;
  try{
   if(r&&!r.attemptId&&Date.now()-r.created>=86400000)throw new Error('This command is outside its safe recovery window. Inspect saved planning history before making another request.');
   if(!r){if(stale)throw new Error('Review the changed project context before making a new proposal.');r={key:crypto.randomUUID(),requestKey:crypto.randomUUID(),input:{kind,request_id:snapshot.current_brain.content.original_request_id,base_brain_revision_id:bases.brain,base_version_id:bases.version},intent,created:Date.now()};save(r);}
   if(r.input.kind==='change'&&r.input.request_id===snapshot.current_brain.content.original_request_id){
    const recorded=await projectRequest<components['schemas']['RequestRecord']>(`/projects/${id}/requests`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':r.requestKey},body:JSON.stringify({text:r.intent,base_brain_revision_id:r.input.base_brain_revision_id,base_version_id:r.input.base_version_id})});r={...r,input:{...r.input,request_id:recorded.id}};save(r);
   }
   let value=r.attemptId?await projectRequest<Attempt>(`${path}/attempts/${r.attemptId}`):await projectRequest<Attempt>(`${path}/attempts`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':r.key},body:JSON.stringify(r.input)});r={...r,attemptId:value.id};save(r);
   if(await finish(value))return;
   const controller=new AbortController();pollRef.current=controller;
   const started=Date.now();while(Date.now()-started<135000&&!controller.signal.aborted){await new Promise(resolve=>setTimeout(resolve,1000));if(controller.signal.aborted)return;value=await projectRequest<Attempt>(`${path}/attempts/${value.id}`,{signal:controller.signal});if(await finish(value))return;}
  }catch(e){if(pollRef.current?.signal.aborted)return;if(e instanceof ProjectAPIError&&e.status>=400&&e.status<500&&e.code!=='IDEMPOTENCY_IN_PROGRESS'){save(null);await refresh();}if(!(e instanceof DOMException&&e.name==='AbortError'))setError(e instanceof Error?e.message:'Planning unavailable. Your intent is preserved.');}
  finally{busyRef.current=false;setBusy(false);}
 }
 async function cancel(){if(!attempt||attempt.status!=='pending')return;try{const value=await projectRequest<Attempt>(`${path}/attempts/${attempt.id}/cancel`,{method:'POST'});pollRef.current?.abort();await finish(value);}catch(e){setError(e instanceof Error?e.message:'Cancellation unavailable.');}}
 async function review(record:Proposal){if(busyRef.current)return;busyRef.current=true;setBusy(true);setError('');try{await projectRequest(`${path}/proposals/${record.id}/review`,{method:'POST'});await refresh();history.retry();}catch(e){setError(e instanceof Error?e.message:'Review unavailable.');}finally{busyRef.current=false;setBusy(false);}}
 const records=history.data?.items??[];
 return <div className="workspace-document">{(!records.length||editorOpen)&&<div className="planning-heading"><span className="meta">PROJECT PLANNING / PROPOSED WORK</span><h2>{records.length&&!editorOpen?'Review your plan':snapshot.current_version?'Plan your next change':'Plan your app'}</h2><p>Review the proposed work. Approve it when the direction is right.</p></div>}
 <details className="planning-context"><summary>Project context and usage</summary>{usage.data&&<p>Planning allowance today: {usage.data.requests_used} of {usage.data.requests_per_day} requests; {usage.data.tokens_reserved.toLocaleString()} of {usage.data.daily_token_budget.toLocaleString()} tokens reserved. Resets {time(usage.data.resets_at)}. Up to {usage.data.requests_per_minute} requests per minute; one pending attempt at a time. No automatic model retries.</p>}
 <p>Brain revision {snapshot.current_brain.revision} · {snapshot.current_version?`${snapshot.current_version.mode==='real'?'Version':'Demo version'} ${snapshot.current_version.number}`:'No successful version'}. {snapshot.current_version?.mode==='real'?'This plan uses the current saved source.':'No verified generated source exists.'}</p></details>
 {error&&<p role="alert" className="workspace-notice">{error}</p>}{stale&&<div className="workspace-notice"><p>Your draft context changed. Text is preserved.</p><button className="button button-secondary" disabled={busy||!!receipt} onClick={()=>setBases({brain:snapshot.project.current_brain_revision_id,version:snapshot.project.current_version_id})}>Use reviewed current context</button></div>}
 {receipt&&!busy&&<div className="workspace-notice">{!receipt.attemptId&&Date.now()-receipt.created>=86400000?<p role="alert">This command is outside its safe recovery window. Inspect saved planning history before making another request.</p>:<><p>A saved planning request is awaiting confirmation.</p><button className="button button-secondary" onClick={()=>void run(receipt!.input.kind)}>Resolve saved planning command</button></>}</div>}
 <details className="planning-request-editor" open={editorOpen} onToggle={event=>setEditorOpen(event.currentTarget.open)}><summary>{snapshot.current_version?'Describe a change':records.length?'Plan another direction':'Make your first plan'}</summary>
 <button className={!snapshot.current_version&&!records.length&&intent.trim().length<20?"button button-primary":"button button-secondary"} disabled={!ready||busy||stale||!!receipt||!!snapshot.project.archived_at} onClick={()=>void run('initial')}>Plan from original brief</button>
 <div className="form-field"><label htmlFor="planning-intent">Describe the change</label><textarea id="planning-intent" rows={5} maxLength={10000} value={intent} disabled={busy||!!receipt} onChange={e=>setIntent(e.target.value)} placeholder="For example: add a priority filter to the leads list and keep the existing layout."/><p className="field-hint">{snapshot.current_version?'Your original brief and any live release stay unchanged while you plan the update.':'Your saved brief stays unchanged while you explore a different direction.'}</p></div>
 <button className={intent.trim().length>=20?"button button-primary":"button button-secondary"} disabled={!ready||busy||stale||!!receipt||intent.trim().length<20||!!snapshot.active_run||!!snapshot.project.archived_at} onClick={()=>void run('change')}>Plan this change</button>
 {snapshot.active_run&&<p>Wait for the active build to finish before recording a change.</p>}{busy&&<p role="status">{attempt?.status==='pending'?'Planning is pending; checking its saved status…':'Saving your planning request…'}</p>}{attempt?.status==='pending'&&<button className="button button-secondary" onClick={()=>void cancel()}>Cancel planning</button>}
 {attempt&&<details><summary>Planning attempt details</summary><p className="meta">Planning attempt: {attempt.status} · reserved token allowance {attempt.reserved_tokens}{attempt.input_tokens!==null?` · provider-reported input ${attempt.input_tokens}`:''}{attempt.output_tokens!==null?` · provider-reported output ${attempt.output_tokens}`:''}. These are planning usage fields, not application execution evidence.</p></details>}
 </details>
 <ResourceState {...history}/>{!history.pending&&!records.length&&<p>Your brief is saved. Make the plan for your first version.</p>}{records[0]&&<ProposalView key={`${records[0].id}-${generation}`} record={records[0]} busy={busy} changing={Boolean(snapshot.active_run)||editorOpen&&intent.trim().length>=20} onReview={()=>void review(records[0]!)}/>}{records.length>1&&<details className="earlier-plans"><summary>Earlier plans ({records.length-1})</summary>{records.slice(1).map(record=><ProposalView key={record.id} record={record} busy={busy} changing onReview={()=>void review(record)}/>)}</details>}
 </div>;
}
