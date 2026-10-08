'use client';
import type {BuildProgress} from '@/lib/workspace/build-progress';
import {workspaceTime as time} from '@/lib/workspace/dates';
const statusNames={complete:'Confirmed',active:'Current',waiting:'Waiting',pending:'Pending',failed:'Needs attention',canceled:'Canceled',blocked:'Needs a status check'};
export function BuildTimeline({progress,compact=false}:{progress:BuildProgress;compact?:boolean}){
 return <div className={`build-timeline ${compact?'compact-timeline':''}`} data-state={progress.state}>
  <ol aria-label="Build execution timeline">{progress.steps.map((step,index)=><li key={step.label} data-state={step.state} aria-current={index===progress.stage?'step':undefined}>
   <span className="build-step-marker" aria-hidden="true">{step.state==='complete'?'✓':step.state==='failed'?'!':String(index+1).padStart(2,'0')}</span>
   <div><div className="build-step-heading"><h4>{step.label}</h4><span>{statusNames[step.state]}</span></div>{(index===progress.stage||step.state==='complete'||!compact)&&<p>{step.description}</p>}</div>
  </li>)}</ol>
  {progress.waiting&&<div className="build-wait-notice" role="status"><strong>{progress.state==='blocked'?'Activity cannot be confirmed':'Still waiting for an observed result'}</strong><p>{progress.waiting}</p></div>}
  <p className="build-observation"><span>Last saved step</span><time dateTime={progress.lastObservedAt}>{time(progress.lastObservedAt)}</time>{progress.lastHeartbeatAt&&<><span>Worker check-in</span><time dateTime={progress.lastHeartbeatAt}>{time(progress.lastHeartbeatAt)}</time></>}</p>
 </div>;
}
export function BuildActivity({progress}:{progress:BuildProgress}){
 const terminal=['succeeded','failed','canceled'].includes(progress.run.status);
 const badge=progress.state==='blocked'?statusNames.blocked:progress.run.status==='queued'?'Queued':progress.state==='active'&&progress.repairing?'Repairing':statusNames[progress.state];
 const label=terminal?'SAVED BUILD RESULT':progress.state==='blocked'?'STATUS CHECK REQUIRED':progress.run.status==='queued'?'BUILD ACCEPTED':progress.repairing&&progress.state==='active'?'OBSERVED REPAIR':'SAVED BUILD PROGRESS';
 return <div className="build-activity" data-animated={progress.animate?'true':'false'} data-state={progress.state}>
  <span className="factory-activity" aria-hidden="true"><i/><i/><i/><b/></span>
  <div><span className="meta">{label}</span><h3 aria-live="polite">{progress.title}</h3><p>{progress.description}</p></div>
  <span className="activity-state">{badge}</span>
 </div>;
}
