import { uuid, type StartRun } from './contracts.ts';
export type RunCommand = { action: 'start' | 'retry' | 'cancel'; key: string; input: StartRun | Record<string,never>; runId?: string; started: number };
export function readRunCommand(storage: Pick<Storage,'getItem'>, name: string): RunCommand | null {
  try {
    const value = JSON.parse(storage.getItem(name) ?? 'null');
    if (!value || !['start','retry','cancel'].includes(value.action) || typeof value.key !== 'string' || !uuid.test(value.key) || !Number.isFinite(value.started) || !value.input || typeof value.input !== 'object') return null;
    if (value.action === 'start') {
      if (typeof value.input.request_id !== 'string' || !uuid.test(value.input.request_id) || typeof value.input.expected_brain_revision_id !== 'string' || !uuid.test(value.input.expected_brain_revision_id) || Object.keys(value.input).length !== 2) return null;
    } else if (typeof value.runId !== 'string' || !uuid.test(value.runId) || Object.keys(value.input).length) return null;
    return value;
  } catch { return null; }
}
