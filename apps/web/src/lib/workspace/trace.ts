import type { components } from '@f01/api-client/schema';
import { uuid } from './contracts.ts';
export type BuildEvent = components['schemas']['EventRecord'];
export type TraceState = { sequence: number; events: BuildEvent[]; pending: BuildEvent[] };
export const phases = ['understanding', 'planning', 'building', 'verifying', 'deploying'] as const;
export function eventRecord(value: unknown, project: string): value is BuildEvent {
  if (!value || typeof value !== 'object') return false;
  const v = value as BuildEvent;
  return typeof v.id === 'string' && uuid.test(v.id) && v.project_id === project && Number.isInteger(v.sequence) && v.sequence > 0 && v.sequence <= 2147483647 && typeof v.type === 'string' && typeof v.message === 'string' && v.message.length <= 1000 && (v.mode === null || v.mode === 'simulated' || v.mode === 'real') && (v.phase === null || phases.includes(v.phase)) && ['info','warning','error'].includes(v.severity) && typeof v.payload === 'object' && v.payload !== null && v.payload.schema_version === 1;
}
/** Later events remain pending until every missing project sequence is recovered. */
export function acceptEvents(state: TraceState, incoming: BuildEvent[]): { state: TraceState; gap: boolean; applied: BuildEvent[] } {
  const pending = new Map<number, BuildEvent>();
  for (const event of [...state.pending, ...incoming]) if (event.sequence > state.sequence && !pending.has(event.sequence)) pending.set(event.sequence, event);
  let sequence = state.sequence;
  const applied: BuildEvent[] = [];
  while (pending.has(sequence + 1)) { sequence++; applied.push(pending.get(sequence)!); pending.delete(sequence); }
  return { state: { sequence, events: [...state.events, ...applied], pending: [...pending.values()].sort((a,b) => a.sequence - b.sequence) }, gap: pending.size > 0, applied };
}
export function reconnectDelay(attempt: number, random = Math.random): number { return Math.min(15000, 1000 * 2 ** Math.min(attempt, 4) + random() * 250); }
export function issueRelationships(events: BuildEvent[]) {
  return events.filter(e => e.payload.issue_id).map(issue => ({ issue, repairs: events.filter(e => e.payload.resolves_issue_id === issue.payload.issue_id && e.run_id === issue.run_id) }));
}
