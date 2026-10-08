'use client';
import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from 'react';
import Link from 'next/link';
import {usePathname,useSearchParams} from 'next/navigation';
import type {components} from '@f01/api-client/schema';
import type {Run} from '@/lib/workspace/contracts';
import {observeBuild,buildReadUnavailable,type BuildProgress} from '@/lib/workspace/build-progress';
import {projectJourney} from '@/lib/workspace/journey';
import {productionURL} from '@/lib/workspace/release-receipt';
import {observedRun,acknowledgementObserved} from '@/lib/workspace/command-state';
import {BuildTimeline} from './build-progress';
import {JourneyRail} from './journey-rail';
import {useResource,useWorkspace} from './workspace';
type Resource<T>={data:T|null;error:string;pending:boolean;retry:()=>void};
type Flow={session:Resource<components['schemas']['SessionView']>;plans:Resource<components['schemas']['ProposalList']>;builds:Resource<components['schemas']['BuildList']>;build:Resource<components['schemas']['BuildDetail']>;releases:Resource<components['schemas']['ReleaseWorkspace']>;accepted:Run|null;currentRun:Run|null;acknowledge:(run:Run)=>void;now:number};
const FlowContext=createContext<Flow|null>(null);
export function FlowProvider({children}:{children:ReactNode}){
 const {id,snapshot,refresh}=useWorkspace();
 const session=useResource<components['schemas']['SessionView']>('/session');
 const plans=useResource<components['schemas']['ProposalList']>(`/projects/${id}/planning/proposals`);
 const builds=useResource<components['schemas']['BuildList']>(`/projects/${id}/builds`);
 const releases=useResource<components['schemas']['ReleaseWorkspace']>(`/projects/${id}/releases`);
 const [accepted,setAccepted]=useState<Run|null>(null),[now,setNow]=useState(()=>Date.now());
 const currentRun=observedRun(snapshot,accepted);
 const build=useResource<components['schemas']['BuildDetail']>(currentRun?.mode==='real'?`/projects/${id}/builds/${currentRun.id}`:null,{retainError:true});
 const pending=useRef(build.pending);pending.current=build.pending;
 useEffect(()=>{if(accepted&&acknowledgementObserved(snapshot,accepted))setAccepted(null);},[accepted,snapshot.latest_run?.id,snapshot.latest_run?.status]);
 useEffect(()=>{setAccepted(null);},[id]);
 useEffect(()=>{build.retry();setNow(Date.now());},[snapshot.last_sequence,build.retry]);
 useEffect(()=>{const descriptor=snapshot.current_version?.preview_descriptor;if(descriptor?.kind!=='isolated')return;const timer=setInterval(()=>setNow(Date.now()),5000);return()=>clearInterval(timer);},[snapshot.current_version?.id]);
 const active=snapshot.active_run??accepted;
 useEffect(()=>{if(active?.mode!=='real'||!['queued','running'].includes(active.status))return;let checking=false;
  const timer=setInterval(()=>{setNow(Date.now());if(checking||pending.current)return;checking=true;void refresh(true,false).finally(()=>{build.retry();checking=false;});},2000);
  return()=>clearInterval(timer);
 },[active?.id,active?.mode,active?.status,refresh,build.retry]);
 return <FlowContext.Provider value={{session,plans,builds,build,releases,accepted,currentRun,acknowledge:setAccepted,now}}>{children}</FlowContext.Provider>;
}
export function useFlow(){const flow=useContext(FlowContext);if(!flow)throw Error('Project flow missing');return flow;}
export function useBuildProgress(runOverride?:Run|null):BuildProgress|null{
 const {snapshot,events,transport}=useWorkspace(),flow=useFlow();
 const run=runOverride??flow.currentRun;
 if(!run||run.mode!=='real')return null;
 const currentRead=flow.build.data?.run.id===run.id?flow.build.data:null;
 const detail=currentRead??flow.builds.data?.items.find(item=>item.run.id===run.id)??null;
 return observeBuild({run,detail,events,version:snapshot.current_version,now:flow.now,disconnected:buildReadUnavailable({currentRead:Boolean(currentRead),readError:Boolean(flow.build.error),historyError:Boolean(flow.builds.error),transport})});
}
export function useJourney(){
 const {snapshot,transport}=useWorkspace(),flow=useFlow(),query=useSearchParams(),pathname=usePathname(),progress=useBuildProgress();
 const capabilities=flow.session.data?.capabilities;
 const current=flow.currentRun;
 const observedSnapshot=flow.accepted?{...snapshot,latest_run:current,active_run:current&&['queued','running'].includes(current.status)?current:null}:snapshot;
 return projectJourney({snapshot:observedSnapshot,plans:flow.plans.data,releases:flow.releases.data,progress,deploySelected:query.get('step')==='deploy',changeSelected:pathname.endsWith('/planning')&&query.get('change')==='1',blocked:['session expired','access unavailable'].includes(transport),runtimeAvailable:capabilities?capabilities.execution_mode!=='real'||capabilities.real_generation:undefined,now:flow.now});
}
export function JourneyGuide(){
 const {id,snapshot,transport}=useWorkspace(),journey=useJourney(),query=useSearchParams(),pathname=usePathname(),progress=useBuildProgress();
 const historical=Boolean(query.get('version')),liveURL=productionURL(journey.release?.public_url);
 return <section className="journey-guide journey-v3" aria-label="Current project step" data-current={journey.steps[journey.step]?.label.toLowerCase()} data-state={journey.state}>
  <div className="journey-current"><span className="journey-kicker">{historical?'History · inspection only':snapshot.project.archived_at?'Archived project':journey.update?'Update journey':snapshot.active_run?.mode==='simulated'||snapshot.current_version?.mode==='simulated'?'Demonstration journey':'Project journey'} · Step {journey.step+1} of 6</span><p><strong>{historical?'Viewing a saved version':journey.title}</strong><span>{historical?'Your current version and public release stay unchanged.':journey.next}</span></p></div>
  <JourneyRail journey={journey}/>
  {journey.update&&journey.release&&<div className="journey-live-preserved"><span className="live-dot" aria-hidden="true"/><strong>Last confirmed live release</strong><span>{journey.release.version_id===snapshot.current_version?.id?`Version ${snapshot.current_version.number}`:'Earlier version'} stays recorded while this update progresses.</span>{liveURL&&<a href={liveURL} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Open live product ↗</a>}<details><summary>Release details</summary><p>Version {journey.release.version_id} · Release {journey.release.id}</p></details></div>}
  {journey.step===2&&progress&&['queued','running'].includes(progress.run.status)&&pathname!==`/projects/${id}`&&<details className="journey-build-expanded" open><summary>Build execution · {progress.steps[progress.stage]?.label}</summary><BuildTimeline progress={progress} compact/><Link className="button button-secondary" href={`/projects/${id}?step=build`}>Open active build</Link></details>}
  {snapshot.project.archived_at&&<Link className="text-action" href={`/projects/${id}/settings`}>Open project settings ↗</Link>}
  {transport==='session expired'&&<Link className="button button-primary" href="/sign-in">Sign in to continue</Link>}
 </section>;
}
