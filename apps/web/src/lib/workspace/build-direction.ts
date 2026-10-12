import type {components} from '@f01/api-client/schema';
import type {Run} from './contracts.ts';

type Proposal = components['schemas']['ProposalRecord'];

// Review does not advance Brain. A different saved request/proposal can therefore
// supersede a failed run while retaining the same Brain and base version.
export function proposalReplacesRun(proposal:Proposal|undefined,run:Run|null|undefined):boolean{
 if(!proposal?.current_context||!run||proposal.project_id!==run.project_id)return false;
 const proposed=Date.parse(proposal.created_at),started=Date.parse(run.created_at);
 return proposal.request_id!==run.request_id||proposal.brain_revision_id!==run.input_brain_revision_id||proposal.version_id!==run.base_version_id||Number.isFinite(proposed)&&Number.isFinite(started)&&proposed>started;
}
