'use client';
import {createContext,useContext,type ReactNode} from 'react';
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';
import type {components} from '@f01/api-client/schema';
import {useResource,useWorkspace} from './workspace';

type Resource<T>={data:T|null;error:string;pending:boolean;retry:()=>void};
type Flow={session:Resource<components['schemas']['SessionView']>;plans:Resource<components['schemas']['ProposalList']>;builds:Resource<components['schemas']['BuildList']>;releases:Resource<components['schemas']['ReleaseWorkspace']>};
const FlowContext=createContext<Flow|null>(null);
export function FlowProvider({children}:{children:ReactNode}){
 const {id}=useWorkspace();
 const session=useResource<components['schemas']['SessionView']>('/session');
 const plans=useResource<components['schemas']['ProposalList']>(`/projects/${id}/planning/proposals`);
 const builds=useResource<components['schemas']['BuildList']>(`/projects/${id}/builds`);
 const releases=useResource<components['schemas']['ReleaseWorkspace']>(`/projects/${id}/releases`);
 return <FlowContext.Provider value={{session,plans,builds,releases}}>{children}</FlowContext.Provider>;
}
export function useFlow(){const flow=useContext(FlowContext);if(!flow)throw Error('Project flow missing');return flow;}
export function useJourney(){
 const {snapshot}=useWorkspace(),{plans,releases}=useFlow();
 const proposal=plans.data?.items.find(p=>p.current_context),reviewed=proposal?.reviewed;
 const release=releases.data?.releases.find(r=>r.id===releases.data?.current_release_id);
 const activeRelease=releases.data?.releases.find(r=>!['succeeded','failed','canceled'].includes(r.state));
 const version=snapshot.current_version,active=snapshot.active_run;
 const currentLive=Boolean(version&&release?.version_id===version.id);
 const step=activeRelease?5:active?3:proposal?.current_context&&reviewed?3:proposal?.current_context&&!reviewed?2:version?currentLive?5:4:1;
 const next=activeRelease?'Wait for publishing checks. Your previous release stays recorded.':active?'Follow the saved build steps. Preview appears after verification.':proposal?.current_context&&reviewed?'Build the plan you approved.':proposal?.current_context&&!reviewed?'Review and approve the proposed work.':version?currentLive?'Describe the next change when you are ready.':'Review your verified preview, then publish when ready.':'Make a plan from the brief you saved.';
 return {step,next,proposal,version,release,activeRelease,currentLive};
}
const steps=['Create','Plan','Approve','Build','Preview','Publish'];
export function JourneyGuide(){
 const {id,snapshot,transport}=useWorkspace(),journey=useJourney(),query=useSearchParams();
 const historical=Boolean(query.get('version')),step=query.get('step')==='deploy'?5:journey.step;
 return <section className="journey-guide" aria-label="Current project step">
  <div className="journey-current"><span className="journey-kicker">{historical?'History · inspection only':snapshot.project.archived_at?'Archived project':journey.version&&!journey.currentLive?'Saved version ready':'Your project'}</span><p><strong>{historical?'Viewing a saved version':journey.currentLive&&!journey.activeRelease?'Live':steps[step]}</strong><span>{historical?'Your current version and public release stay unchanged.':transport==='session expired'?'Sign in again to continue. Saved work stays available.':snapshot.project.archived_at?'Unarchive in Settings to continue.':query.get('step')==='deploy'&&!journey.activeRelease&&!journey.currentLive?'Review the publishing controls below. Your preview stays available.':journey.next}</span></p></div>
  <ol aria-label="Project lifecycle">{steps.map((name,n)=><li key={name} data-state={n===step?'current':n<step?'complete':'upcoming'} aria-current={n===step?'step':undefined}><span aria-hidden="true">{n<step?'✓':String(n+1).padStart(2,'0')}</span>{name}</li>)}</ol>
  {snapshot.project.archived_at&&<Link className="text-action" href={`/projects/${id}/settings`}>Open project settings ↗</Link>}
 </section>;
}
