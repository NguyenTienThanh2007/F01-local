import type {Run,Snapshot} from './contracts.ts';
const rank=(status:Run['status'])=>status==='queued'?0:status==='running'?1:2;
export function acknowledgementObserved(snapshot:Pick<Snapshot,'latest_run'>,acknowledged:Run){
 return snapshot.latest_run?.id===acknowledged.id&&rank(snapshot.latest_run.status)>=rank(acknowledged.status);
}
// A confirmed command response is authoritative until a read catches up to it.
export function observedRun(snapshot:Pick<Snapshot,'latest_run'|'active_run'>,acknowledged:Run|null):Run|null{
 return acknowledged&&!acknowledgementObserved(snapshot,acknowledged)?acknowledged:snapshot.active_run??snapshot.latest_run;
}
