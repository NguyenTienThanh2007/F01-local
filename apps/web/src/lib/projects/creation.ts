import type { CreateInput } from './contracts.ts';
export type Attempt = { key: string; input: CreateInput; started: number; owner?: string };
export const ATTEMPT_STORAGE = 'f01.pending-project-creation.v1';
// This is only an unresolved command receipt, never a project inventory or source of truth.
export function readAttempt(storage: Pick<Storage, 'getItem'>): Attempt | null {
  try {
    const data = JSON.parse(storage.getItem(ATTEMPT_STORAGE) ?? 'null');
    if (typeof data?.key === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.key) && typeof data?.input?.brief === 'string' && (data.input.title === null || typeof data.input.title === 'string') && (data.owner===undefined || typeof data.owner==='string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.owner)) && Number.isFinite(data.started) && data.started >= 0 && data.started <= Date.now()) return data as Attempt;
  } catch { /* Storage may be unavailable. The mounted form still retains its receipt. */ }
  return null;
}
export function outcomeIsUnknown(status: number, code: string): boolean {
  return status === 0 || status >= 500 || [408, 425].includes(status) || code === 'IDEMPOTENCY_IN_PROGRESS';
}
export function creationTarget(value: unknown): string | null {
  if (!value || typeof value !== 'object') return null;
  const result = value as Record<string, unknown>, project = result.project as Record<string, unknown> | null;
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!project || typeof project.id !== 'string' || !uuid.test(project.id) || !['real', 'simulated'].includes(String(result.execution_mode))) return null;
  const path = `/projects/${project.id}`;
  return result.project_url === path && typeof result.request_id === 'string' && uuid.test(result.request_id) && typeof result.brain_revision_id === 'string' && uuid.test(result.brain_revision_id) && (result.run_id === null && result.execution_mode === 'real' || typeof result.run_id === 'string' && uuid.test(result.run_id)) ? path : null;
}
