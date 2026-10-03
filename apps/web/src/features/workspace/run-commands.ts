'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { projectRequest, ProjectAPIError } from '@/lib/projects/browser';
import { outcomeIsUnknown } from '@/lib/projects/creation';
import { uuid, type Run, type Snapshot } from '@/lib/workspace/contracts';
import { readRunCommand, type RunCommand } from '@/lib/workspace/run-command';
export function useRunCommands(id: string, refresh: () => Promise<Snapshot | null>) {
  const [pending,setPending] = useState(false), [error,setError] = useState(''), [notice,setNotice] = useState(''), [recovery,setRecovery] = useState<RunCommand | null>(null);
  const busy = useRef(false), receipt = useRef<RunCommand | null>(null), ready = useRef(false);
  const storageKey = `f01.pending-run.v1.${id}`;
  useEffect(() => { try { receipt.current = readRunCommand(sessionStorage,storageKey); setRecovery(receipt.current); } catch { /* mounted recovery remains */ } ready.current = true; },[storageKey]);
  const execute = useCallback(async (command: RunCommand): Promise<Run | null> => {
    if (busy.current || !ready.current) return null;
    if (Date.now() - command.started >= 86400000) { setError('This unresolved run command is outside the 24-hour recovery window. Inspect saved run history before starting another command.'); return null; }
    busy.current = true; receipt.current = command; setRecovery(command); setPending(true); setError(''); setNotice('');
    try { sessionStorage.setItem(storageKey,JSON.stringify(command)); } catch { /* exact receipt retained in memory */ }
    const path = command.action === 'start' ? `/projects/${id}/runs` : `/projects/${id}/runs/${command.runId}/${command.action}`;
    try {
      const run = await projectRequest<Run>(path,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':command.key},body:JSON.stringify(command.input)});
      const input = command.input as { request_id?: string; expected_brain_revision_id?: string };
      if (!uuid.test(run.id) || run.project_id !== id || run.mode !== 'simulated' || (command.action === 'start' && (run.request_id !== input.request_id || run.input_brain_revision_id !== input.expected_brain_revision_id)) || (command.action === 'retry' && run.retry_of_run_id !== command.runId) || (command.action === 'cancel' && run.id !== command.runId)) throw new ProjectAPIError('SERVICE_UNAVAILABLE',0);
      receipt.current = null; setRecovery(null); try { sessionStorage.removeItem(storageKey); } catch { /* no project inventory */ }
      setNotice(command.action === 'cancel' ? `Simulation is ${run.status}. Any successful preview is preserved.` : 'Simulation queued. The bundled sample may remain unchanged; no source, tests or external deployment will run.');
      await refresh(); return run;
    } catch (e) {
      const uncertain = !(e instanceof ProjectAPIError) || outcomeIsUnknown(e.status,e.code) || e.code === 'IDEMPOTENCY_KEY_REUSED';
      if (!uncertain) { receipt.current = null; setRecovery(null); try { sessionStorage.removeItem(storageKey); } catch { /* no inventory */ } }
      setError(e instanceof Error ? e.message : 'Unable to confirm the simulation command.'); await refresh(); return null;
    } finally { busy.current = false; setPending(false); }
  },[id,storageKey,refresh]);
  async function command(action: RunCommand['action'], requestOrRun: string, brain?: string) {
    if (receipt.current) { setError('Resolve the saved run command first. Its exact key and context are retained.'); return null; }
    return execute({action,key:crypto.randomUUID(),started:Date.now(),input:action === 'start' ? {request_id:requestOrRun,expected_brain_revision_id:brain!} : {},...(action === 'start' ? {} : {runId:requestOrRun})});
  }
  return { pending,error,notice,recovery,start:(request: string,brain: string) => command('start',request,brain),retry:(run: string) => command('retry',run),cancel:(run: string) => command('cancel',run),resume:() => receipt.current ? execute(receipt.current) : Promise.resolve(null) };
}
