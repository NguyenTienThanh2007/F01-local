import type {components} from '@f01/api-client/schema';
import type {Snapshot} from './contracts.ts';
import type {BuildProgress,ObservedState} from './build-progress.ts';
export const journeySteps=['Describe','Plan','Build','Preview','Deploy','Live'] as const;
type Plans=components['schemas']['ProposalList'];
type Releases=components['schemas']['ReleaseWorkspace'];
export function projectJourney({snapshot,plans,releases,progress,deploySelected=false,changeSelected=false,blocked=false,runtimeAvailable,now}:{snapshot:Snapshot;plans:Plans|null;releases:Releases|null;progress:BuildProgress|null;deploySelected?:boolean;changeSelected?:boolean;blocked?:boolean;runtimeAvailable?:boolean;now:number}){
 const proposal=plans?.items.find(p=>p.current_context);
 const version=snapshot.current_version;
 const release=releases?.releases.find(r=>r.id===releases.current_release_id&&r.state==='succeeded'&&r.project_id===snapshot.project.id);
 const activeRelease=releases?.releases.find(r=>r.project_id===snapshot.project.id&&!['succeeded','failed','canceled'].includes(r.state));
 const latestRelease=releases?.releases.find(r=>r.project_id===snapshot.project.id&&r.version_id===version?.id&&r.id!==releases.current_release_id);
 const releaseAttention=Boolean(release&&latestRelease&&['failed','canceled'].includes(latestRelease.state)&&Date.parse(latestRelease.created_at)>Date.parse(release.created_at));
 const currentLive=Boolean(version?.mode==='real'&&release?.version_id===version.id);
 const latest=snapshot.latest_run;
 const changedAfterLive=Boolean(release&&latest?.base_version_id&&Date.parse(latest.created_at)>Date.parse(release.created_at)&&['failed','canceled'].includes(latest.status));
 const update=Boolean(release&&(snapshot.active_run||activeRelease||releaseAttention||proposal?.kind==='change'||version?.id!==release.version_id||changedAfterLive||changeSelected));
 const currentFailure=progress&&['failed','canceled'].includes(progress.run.status)&&(!version||progress.run.base_version_id===version.id)&&(!release||changedAfterLive||!currentLive);
 const prep=releases?.preparations.find(p=>p.version_id===version?.id);
 const previewExpired=version?.mode==='real'&&version.preview_descriptor.kind==='isolated'&&(!Number.isFinite(Date.parse(version.preview_descriptor.expires_at))||Date.parse(version.preview_descriptor.expires_at)<=now);
 let step=1,state:ObservedState='waiting',next='Make a plan from your saved brief.',title='Plan your application';
 const building=snapshot.active_run??(progress&&['queued','running'].includes(progress.run.status)?progress.run:null);
 if(activeRelease){step=4;state=activeRelease.state==='reconciling'||activeRelease.state==='restoring'?'waiting':'active';title='Publishing your version';next='Follow the saved publishing checks. The next public release is unconfirmed until those checks pass.';}
 else if(building){step=2;state=progress?.state??(building.status==='queued'?'waiting':'active');title=building.mode==='simulated'?'Demonstration in progress':progress?.title??'Build in progress';next=building.mode==='simulated'?'Follow saved simulation steps. This demonstration does not generate or deploy an application.':progress?.waiting??'Follow the observed build steps. Preview appears automatically after verification and publication.';}
 else if(currentFailure){step=2;state=progress.state;title=progress.title;next=progress.run.status==='canceled'?'Review the saved plan before starting another build.':'Inspect the failed check, then safely retry the saved plan or plan a change.';}
 else if(proposal){if(proposal.reviewed){step=2;title='Ready to build';next='Build the plan you approved.';}else{step=1;state='active';title='Review your plan';next='Review and approve the proposed work before building.';}}
 else if(changeSelected&&release){step=1;title='Plan your update';next='Describe the change. Your last confirmed live release stays recorded.';}
 else if(releaseAttention){step=4;state=latestRelease?.state==='canceled'?'canceled':'failed';title=state==='canceled'?'Publishing canceled':'Deployment needs attention';next='Inspect the saved publishing result. The last confirmed live release stays recorded while you review the next attempt.';}
 else if(currentLive){step=5;state='complete';title='Your product is live';next='Describe the next change when you are ready.';}
 else if(version){
  step=3;title='Review your preview';next='Try the verified version, then continue to publishing.';
  if(previewExpired){state='blocked';title='Preview needs attention';next='The isolated preview expired. Inspect its saved evidence or plan a new build for a fresh preview.';}
  else if(version.mode==='real'&&(deploySelected||prep||releases?.hosting_setup&&!['failed','ready'].includes(releases.hosting_setup.state))){step=4;state=prep?.state==='failed'?'failed':prep?.state==='queued'||prep?.state==='packaging'?'active':'waiting';title=state==='failed'?'Publishing needs attention':'Publish your version';next=state==='failed'?'Review the failed package and plan a corrected version.':prep?.state==='queued'||prep?.state==='packaging'?'The production package is being prepared from your saved version.':'Review the publishing controls. Publishing is a separate decision.';}
  if(latestRelease?.state==='failed'&&step===4){state='failed';title='Deployment needs attention';next='Inspect the failed deployment. Retry only the same reviewed package when the provider is ready.';}
  else if(latestRelease?.state==='canceled'&&step===4){state='canceled';title='Publishing canceled';next='Cancellation is saved. Review the verified package before publishing again; the last confirmed live release stays recorded.';}
  if(releases?.hosting_setup?.state==='failed'&&step===4){state='failed';title='Hosting setup needs attention';next='Review the saved hosting error and safely retry setup before publishing.';}
 }
 if(step===2&&!building&&runtimeAvailable===false){state='blocked';title='Build runtime unavailable';next='Your approved plan is saved. Open Settings to review the required build runtime.';}
 if(snapshot.project.archived_at){state='blocked';next='Unarchive in Settings to continue. Saved history stays preserved.';}
 if(blocked){state='blocked';next='Restore workspace access to confirm current activity. Showing the last saved state.';}
 // A later route or selected view is never evidence of completed work.
 const done=[true,Boolean(proposal?.reviewed||progress?.published||building?.mode==='real'||version&&!update||progress&&progress.run.base_version_id&&['failed','canceled'].includes(progress.run.status)),Boolean(version&&!update||progress?.published),Boolean(version&&!previewExpired&&(!update||progress?.published)),Boolean(currentLive&&!update),Boolean(currentLive&&!update)];
 const steps=journeySteps.map((label,index)=>({label,state:(index===step?state:done[index]?'complete':'pending') as ObservedState}));
 return {step,state,title,next,steps,update,proposal,version,release,activeRelease,currentLive,previewExpired};
}
