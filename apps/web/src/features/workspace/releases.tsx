'use client';
import {useEffect,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import Link from 'next/link';
import type {components} from '@f01/api-client/schema';
import {projectRequest,ProjectAPIError} from '@/lib/projects/browser';
import {outcomeIsUnknown} from '@/lib/projects/creation';
import {readReceipt,saveReceipt} from '@/lib/workspace/receipt-storage';
import {releaseReceipt,releaseReceiptExpired,productionURL,type ReleaseReceipt} from '@/lib/workspace/release-receipt';
import {uuid} from '@/lib/workspace/contracts';
import {useWorkspace,useResource,ResourceState,time} from './workspace';
type Releases=components['schemas']['ReleaseWorkspace'];
const terminal=['succeeded','failed','canceled'];
const stages:Record<string,string>={queued:'Deployment queued',staging:'Staging your package',checking:'Checking the staged app',promoting:'Promoting your release',verifying:'Verifying the public URL',reconciling:'Confirming provider state',restoring:'Restoring the previous release',succeeded:'Deployment verified',failed:'Deployment needs attention',canceled:'Deployment canceled'};
function PublishOptions({sameVersion,children}:{sameVersion:boolean;children:ReactNode}){return sameVersion?<details className="release-publish-options"><summary>Publish this version again</summary>{children}</details>:children;}
export function ReleasePanel({historyOnly=false,versionId}:{historyOnly?:boolean;versionId?:string}){
 const {id,snapshot,refresh}=useWorkspace(),result=useResource<Releases>(`/projects/${id}/releases`);
 const [receipt,setReceipt]=useState<ReleaseReceipt|null>(null),[ready,setReady]=useState(false),[pending,setPending]=useState(false),[error,setError]=useState(''),[reviewed,setReviewed]=useState(false),[notice,setNotice]=useState('');
 const busy=useRef(false),receiptName=`f01:release:${id}`;
 useEffect(()=>{setReceipt(readReceipt(receiptName,v=>releaseReceipt(v,id)));setReady(true);},[id,receiptName]);
 const data=result.data,version=snapshot.current_version,config=data?.configuration,current=data?.releases.find(r=>r.id===data.current_release_id),active=data?.releases.find(r=>!terminal.includes(r.state));
 const prep=data?.preparations.find(p=>p.version_id===version?.id&&p.configuration_id===config?.id),artifact=data?.artifacts.find(a=>a.id===prep?.artifact_id&&a.version_id===version?.id&&a.brain_revision_id===snapshot.project.current_brain_revision_id);
 const setup=data?.hosting_setup;
 const retryRelease=data?.releases.find(r=>['failed','canceled'].includes(r.state)&&r.artifact_id===artifact?.id);
 const waiting=active||prep&&['queued','packaging'].includes(prep.state)||setup&&['queued','creating','reconciling'].includes(setup.state);
 useEffect(()=>{if(!waiting)return;const timer=setInterval(()=>result.retry(),2000);return()=>clearInterval(timer);},[Boolean(waiting),active?.id,prep?.state,setup?.state,result.retry]);
 useEffect(()=>{setReviewed(false);},[artifact?.id,data?.target_generation,snapshot.project.current_brain_revision_id]);
 async function perform(command:ReleaseReceipt){
  if(busy.current||!ready||releaseReceiptExpired(command))return;
  busy.current=true;setPending(true);setError('');setNotice('');setReceipt(command);saveReceipt(receiptName,command);
  try{
   const confirmed=await projectRequest<{id:string;project_id:string}>(command.path,{method:'POST',headers:{'Idempotency-Key':command.key},body:JSON.stringify(command.body)});
   if(!confirmed||!uuid.test(confirmed.id)||confirmed.project_id!==id)throw new ProjectAPIError('SERVICE_UNAVAILABLE',0);
   saveReceipt(receiptName,null);setReceipt(null);setNotice('Command saved. You can leave and return to this project.');setReviewed(false);result.retry();await refresh(true);
  }catch(e){setError(e instanceof Error?e.message:'Release command unavailable.');if(e instanceof ProjectAPIError&&!outcomeIsUnknown(e.status,e.code)&&e.code!=='IDEMPOTENCY_KEY_REUSED'){saveReceipt(receiptName,null);setReceipt(null);}}
  finally{busy.current=false;setPending(false);}
 }
 function send(path:string,body:ReleaseReceipt['body']){void perform({key:crypto.randomUUID(),path,body,created:Date.now()});}
 async function resume(){if(!active||busy.current)return;busy.current=true;setPending(true);try{await projectRequest(`/projects/${id}/releases/${active.id}/resume`,{method:'POST',body:'{}'});result.retry();}catch(e){setError(e instanceof Error?e.message:'Observation recovery unavailable.');}finally{busy.current=false;setPending(false);}}
 async function cancel(){if(!active||busy.current)return;busy.current=true;setPending(true);setError('');try{await projectRequest(`/projects/${id}/releases/${active.id}/cancel`,{method:'POST',body:'{}'});result.retry();}catch(e){setError(e instanceof Error?e.message:'Cancellation unavailable.');}finally{busy.current=false;setPending(false);}}
 const history=data?.releases.filter(r=>!versionId||r.version_id===versionId),liveURL=productionURL(current?.public_url);
 if(!data)return <ResourceState {...result}/>;
 return <section className="workspace-notice production-release" data-state={active?.state??(current?'succeeded':'idle')} aria-label="Production release">
  <span className="meta">02 / PRODUCTION</span><h3>{active?stages[active.state]:current?'Your product is live':'Deploy your product'}</h3>
  {current&&<p>Live release from {current.version_id===version?.id?`version ${version.number}`:'an earlier version'}. {liveURL&&<a className="text-action" href={liveURL} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Open public URL ↗</a>}</p>}
  {current&&version&&current.version_id!==version.id&&<p>Preview version {version.number} is ahead of production. Review and redeploy it when ready.</p>}
  {active&&<p role="status">{active.state==='reconciling'?'The provider outcome is still being confirmed. Your last verified release remains recorded; further changes wait for reconciliation.':active.state==='restoring'?'The update did not pass. F01 is confirming restoration of the previous release.':'Deployment progress is saved. The public link appears after provider and health checks pass.'}</p>}
  {!historyOnly&&!data.available&&<>{data.setup_available&&version?.mode==='real'&&!snapshot.active_run&&!snapshot.project.archived_at?<>{setup?<p role={setup.state==='failed'?'alert':'status'}>{setup.state==='failed'?`Hosting setup needs attention: ${setup.error_code}.`:'Setting up your separate production hosting target. Provider state is saved and checked before a retry.'}</p>:receipt?<button className="button button-secondary" disabled={pending||!ready||releaseReceiptExpired(receipt)} onClick={()=>void perform(receipt)}>Resolve saved hosting command</button>:<><p>Set up a separate Vercel target for this application, then prepare the version you previewed.</p><button className="button button-secondary" disabled={pending||!ready} onClick={()=>send(`/projects/${id}/release-target`,{expected_version_id:version.id,expected_brain_revision_id:snapshot.project.current_brain_revision_id})}>Set up production hosting</button></>}</>:<p>Production hosting is not configured for this project yet. Your saved source, verification and preview remain available.</p>}</>}
  {!historyOnly&&current&&version&&current.version_id===version.id&&!snapshot.active_run&&!active&&!snapshot.project.archived_at&&<Link className="button button-primary" href={`/projects/${id}/planning`}>Plan the next update</Link>}
  {!historyOnly&&data.available&&version?.mode==='real'&&!snapshot.project.archived_at&&!snapshot.active_run&&!active&&<PublishOptions sameVersion={current?.version_id===version.id&&!receipt}>
   {receipt?<><p role="status">A release command is awaiting confirmation. Its exact package, context and key are retained.</p>{releaseReceiptExpired(receipt)?<p role="alert">This receipt is outside its recovery window. Inspect saved release history before issuing another command.</p>:<button className="button button-secondary" disabled={pending||!ready} onClick={()=>void perform(receipt)}>Resolve saved release command</button>}</>:prep&&['queued','packaging'].includes(prep.state)?<p role="status">{prep.state==='queued'?'Production package queued.':'Building and checking your production package.'} This uses the saved version you previewed.</p>:artifact?<>
    <p>Production package verified for version {version.number}. Deploying publishes this exact package to {productionURL(config?.public_url)}.</p>
    <label className="release-review"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/> I reviewed this version and want to publish it.</label>
    <button className="button button-primary" disabled={!reviewed||pending||!ready} onClick={()=>send(`/projects/${id}/releases${retryRelease?`/${retryRelease.id}/retry`:''}`,{artifact_id:artifact.id,configuration_id:config!.id,expected_brain_revision_id:snapshot.project.current_brain_revision_id,expected_version_id:version.id,expected_production_release_id:data.current_release_id,expected_target_generation:data.target_generation})}>{pending?'Saving deployment…':retryRelease?'Retry reviewed deployment':current?'Redeploy reviewed version':'Deploy reviewed version'}</button>
    <details><summary>Package and verification details</summary><p>Package {artifact.digest}</p><p>Source {String(artifact.manifest.source_digest)} · Brain {artifact.brain_revision_id}</p><p>Profile: static application · no server functions or application database</p><p>Verified {time(artifact.created_at)}</p></details>
   </>:prep?.state==='failed'?<p role="alert">Production packaging failed: {prep.error_code}. Your previous preview and release are preserved. Review source and record a change before preparing an updated version.</p>:<><p>Preview your verified application, then prepare its production package.</p><button className="button button-primary" disabled={pending||!ready} onClick={()=>send(`/projects/${id}/release-artifacts`,{version_id:version.id,configuration_id:config!.id,expected_brain_revision_id:snapshot.project.current_brain_revision_id})}>Prepare production package</button></>}
  </PublishOptions>}
  {active&&receipt&&!historyOnly&&<button className="button button-secondary" disabled={pending||!ready||releaseReceiptExpired(receipt)} onClick={()=>void perform(receipt)}>Resolve saved release command</button>}
  {active?.state==='reconciling'&&!historyOnly&&<button className="button button-secondary" disabled={pending} onClick={()=>void resume()}>Resume provider observation</button>}
  {active&&!historyOnly&&<button className="button button-secondary" disabled={pending} onClick={()=>void cancel()}>Request deployment cancellation</button>}
  {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}<ResourceState {...result}/>
  {Boolean(history?.length)&&<details open={historyOnly}><summary>Release history</summary>{history?.map(r=><article className="release-record" key={r.id}><p><strong>{stages[r.state]}</strong>{r.id===data.current_release_id?' · Current production':''} · {time(r.created_at)}</p>{r.error_code&&<p>{r.error_code.replaceAll('_',' ').toLowerCase()}</p>}<p>{r.version_id===version?.id?`Version ${version.number}`:'Earlier saved version'}</p>{r.state==='succeeded'&&productionURL(r.deployment_url)&&<a className="text-action" href={productionURL(r.deployment_url)!} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Open retained deployment ↗</a>}<details><summary>Release references</summary><p>Version {r.version_id} · Release {r.id} · Package {r.artifact_id}</p>{r.last_observed_at&&<p>Last observed {time(r.last_observed_at)}</p>}</details></article>)}</details>}
 </section>;
}
