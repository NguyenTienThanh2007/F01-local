import type { CreateInput } from './contracts.ts';
export type Attempt = { key: string; input: CreateInput; started: number };
export const ATTEMPT_STORAGE = 'f01.pending-project-creation.v1';
// This is only an unresolved command receipt, never a project inventory or source of truth.
export function readAttempt(storage: Pick<Storage, 'getItem'>): Attempt | null {
  try {
    const data = JSON.parse(storage.getItem(ATTEMPT_STORAGE) ?? 'null');
    if (typeof data?.key === 'string' && /^[0-9a-f-]{36}$/i.test(data.key) && typeof data?.input?.brief === 'string' && (data.input.title === null || typeof data.input.title === 'string') && typeof data.started === 'number') return data as Attempt;
  } catch { /* Storage may be unavailable. The mounted form still retains its receipt. */ }
  return null;
}
export function outcomeIsUnknown(status: number, code: string): boolean {
  return status === 0 || status >= 500 || code === 'IDEMPOTENCY_IN_PROGRESS';
}
