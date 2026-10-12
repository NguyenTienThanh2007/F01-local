import type {projectJourney} from '@/lib/workspace/journey';
const labels={complete:'Confirmed',active:'Active',waiting:'Waiting',pending:'Pending',failed:'Needs attention',canceled:'Canceled',blocked:'Blocked'};
export function JourneyRail({journey}:{journey:ReturnType<typeof projectJourney>}){
 return <ol aria-label="Project lifecycle">{journey.steps.map(({label,state},index)=><li key={label} data-state={state} aria-current={index===journey.step?'step':undefined}><span aria-hidden="true">{state==='complete'?'✓':state==='failed'?'!':String(index+1).padStart(2,'0')}</span><strong>{label}</strong><small>{labels[state]}</small></li>)}</ol>;
}
