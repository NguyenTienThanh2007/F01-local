'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ProjectPulse } from '@/features/project-pulse/project-pulse';
import { ProjectPlanningForm } from '@/features/project-planning/project-planning-form';
import { ProjectStarters, projectStarters } from '@/features/project-planning/project-starters';
import { projectRequest, ProjectAPIError } from '@/lib/projects/browser';
import { createInput, type Created, type Session } from '@/lib/projects/contracts';
import { ATTEMPT_STORAGE, readAttempt, outcomeIsUnknown, creationTarget, type Attempt } from '@/lib/projects/creation';

export function ProjectCreation({ initialIdea, planning = false }: { initialIdea: string; planning?: boolean }) {
  const router = useRouter();
  const [mode, setMode] = useState<'create' | 'plan'>(planning ? 'plan' : 'create');
  const [title, setTitle] = useState(''), [brief, setBrief] = useState(initialIdea), [error, setError] = useState(''), [pending, setPending] = useState(false), [unknown, setUnknown] = useState(false), [ready, setReady] = useState(false);
  const attempt = useRef<Attempt | null>(null), busy = useRef(false), briefRef = useRef<HTMLTextAreaElement>(null);
  const [executionMode, setExecutionMode] = useState<'real' | 'simulated' | null>(null);
  useEffect(() => {
    let saved: Attempt | null = null;
    try { saved = readAttempt(sessionStorage); } catch { /* Private browsing may block storage. */ }
    if (saved) { attempt.current = saved; setTitle(saved.input.title ?? ''); setBrief(saved.input.brief); setUnknown(true); setMode('create'); }
    setReady(true);
    const controller = new AbortController();
    void projectRequest<Session>('/session', { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setExecutionMode(value.capabilities?.execution_mode ?? null); }).catch(() => { /* Saving reports its own actionable error. */ });
    return () => controller.abort();
  }, []);
  function forgetReceipt() { attempt.current = null; try { sessionStorage.removeItem(ATTEMPT_STORAGE); } catch { /* memory receipt still works */ } }
  async function create() {
    if (busy.current || !ready) return;
    const input = createInput(title, brief);
    if (!input) { setError('Use an optional title of up to 100 characters and a brief of 20–10,000 characters.'); briefRef.current?.focus(); return; }
    if (attempt.current && Date.now() - attempt.current.started >= 24 * 60 * 60 * 1000) { setError('This unresolved creation is older than the 24-hour recovery window. Check your saved Projects before starting another brief.'); return; }
    const command = attempt.current ?? { key: crypto.randomUUID(), input, started: Date.now() };
    attempt.current = command;
    try { sessionStorage.setItem(ATTEMPT_STORAGE, JSON.stringify(command)); } catch { /* Keep the same receipt in memory when storage is blocked. */ }
    busy.current = true; setPending(true); setError('');
    try {
      const result = await projectRequest<Created>('/projects', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': command.key }, body: JSON.stringify(command.input) });
      const target = creationTarget(result);
      if (!target) throw new ProjectAPIError('SERVICE_UNAVAILABLE', 0);
      forgetReceipt(); setUnknown(false);
      router.push(target);
    } catch (reason) {
      const unresolved = !(reason instanceof ProjectAPIError) || outcomeIsUnknown(reason.status, reason.code) || reason.code === 'IDEMPOTENCY_KEY_REUSED';
      setUnknown(unresolved); if (!unresolved) forgetReceipt();
      setError(reason instanceof Error ? reason.message : 'Creation could not be confirmed. Retry the same brief safely.');
      busy.current = false; setPending(false);
    }
  }
  const locked = pending || unknown;
  return <>
    <div className="creation-modes" role="group" aria-label="Project creation options"><button className={mode === 'create' ? 'active-mode' : ''} aria-pressed={mode === 'create'} disabled={pending} onClick={() => setMode('create')}>Save a project</button><button className={mode === 'plan' ? 'active-mode' : ''} aria-pressed={mode === 'plan'} disabled={locked} onClick={() => setMode('plan')}>Explore a draft plan</button></div>
    {mode === 'plan' ? <ProjectPlanningForm initialIdea={initialIdea} companion={<aside className="planning-guide"><span className="meta">DRAFT PLANNING / OPTIONAL</span><h2>A direction to review.</h2><p>This existing planning tool creates a real structured proposal. It stays on this page and is not saved as a project or Brain revision.</p><p>Use Save a project when you are ready to persist your original brief.</p></aside>} /> : <div className="planning-composition project-creation-composition">
      <form className="project-form saved-project-form" onSubmit={event => { event.preventDefault(); void create(); }} noValidate aria-busy={pending}>
        <div className="composer-topline"><span className="meta">PROJECT / ORIGINAL BRIEF</span><ProjectPulse state={pending ? 'thinking' : 'idle'} label={pending ? 'Confirming save' : unknown ? 'Save awaiting confirmation' : 'Ready for your brief'} /></div>
        <label className="create-title-label" htmlFor="new-project-title">Project title <span>Optional · up to 100 characters</span></label><input id="new-project-title" name="title" value={title} readOnly={locked} onChange={event => setTitle(event.target.value)} placeholder="Give your project a name" />
        <div className="brief-label"><label htmlFor="saved-project-brief">Product brief</label><span className="meta">20–10,000 CHARACTERS</span></div><textarea ref={briefRef} id="saved-project-brief" name="brief" rows={7} value={brief} readOnly={locked} onChange={event => setBrief(event.target.value)} placeholder="What should exist? Who is it for? What should get better?" aria-required="true" aria-invalid={Boolean(error)} aria-describedby="saved-brief-help creation-boundary" />
        <div className="brief-support"><p id="saved-brief-help">Your original request will be preserved.</p><span className="meta">{Array.from(brief).length.toLocaleString('en-US')} / 10,000</span></div>
        {unknown && <div className="unresolved-creation" role="status">The previous save has not been confirmed. Retry uses the same brief and creation key to recover the existing result. Keep this tab until the result is known.</div>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="planning-actions"><button className="button button-primary" disabled={pending || !ready}>{pending ? 'Saving project…' : unknown ? 'Retry project creation' : executionMode === 'simulated' ? 'Create demo project' : 'Create project'}</button><span className="meta">BRIEF → PERSISTED PROJECT</span></div>
        <p className="composer-note" id="creation-boundary">{executionMode === 'simulated' ? <><strong>Demo mode.</strong> Your brief and project history are saved. A server-owned demonstration publishes a bundled sample on success.</> : <>Your brief and project history are saved. Review a plan in your workspace before starting a build. Saving alone does not build or deploy your application.</>}</p>
        <ProjectStarters selected={projectStarters.find(item => item.brief === brief)?.id} disabled={locked} onSelect={id => { setBrief(projectStarters.find(item => item.id === id)!.brief); setError(''); briefRef.current?.focus(); }} />
      </form>
      <aside className="planning-guide" aria-labelledby="save-guide"><span className="meta">WHAT HAPPENS NEXT</span><h2 id="save-guide">A project you<br />can return to.</h2><ol><li><span className="meta">01</span><div><h3>Set the intention</h3><p>A title and an original brief. Plain language is enough.</p></div></li><li><span className="meta">02</span><div><h3>Confirm the save</h3><p>The server saves your project and its initial context together. A safe retry recovers the same result.</p></div></li><li><span className="meta">03</span><div><h3>Keep it in your workspace</h3><p>Reload, find it, rename it and manage its archive state.</p></div></li></ol><div className="guide-boundary"><span className="meta">DESCRIBE → PLAN → BUILD → PREVIEW</span><p>Open your saved workspace to review the plan, follow progress and inspect version history.</p></div></aside>
    </div>}
  </>;
}
