'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ProjectPulse } from '@/features/project-pulse/project-pulse';
import { ProjectPlanningForm } from '@/features/project-planning/project-planning-form';
import { ProjectStarters, projectStarters } from '@/features/project-planning/project-starters';
import { projectRequest, ProjectAPIError } from '@/lib/projects/browser';
import { createInput, type Created, type Session } from '@/lib/projects/contracts';
import { ATTEMPT_STORAGE, readAttempt, outcomeIsUnknown, creationTarget, readCreationDraft,saveCreationDraft, type Attempt } from '@/lib/projects/creation';

export function ProjectCreation({ initialIdea, planning = false }: { initialIdea: string; planning?: boolean }) {
  const router = useRouter();
  const [mode, setMode] = useState<'create' | 'plan'>(planning ? 'plan' : 'create');
  const [title, setTitle] = useState(''), [brief, setBrief] = useState(initialIdea), [error, setError] = useState(''), [pending, setPending] = useState(false), [unknown, setUnknown] = useState(false), [ready, setReady] = useState(false);
  const attempt = useRef<Attempt | null>(null), busy = useRef(false), briefRef = useRef<HTMLTextAreaElement>(null);
  const [requiresSignIn,setRequiresSignIn]=useState(false),[accountBlocked,setAccountBlocked]=useState(false),[invalid,setInvalid]=useState(false);
  const draftOwner=useRef<string|null|undefined>(undefined),edited=useRef(false);
  const [draftReady,setDraftReady]=useState(false),[draftRestored,setDraftRestored]=useState(false);
  const [executionMode, setExecutionMode] = useState<'real' | 'simulated' | null>(null);
  useEffect(() => {
    let saved: Attempt | null = null;
    try { saved = readAttempt(sessionStorage); } catch { /* Private browsing may block storage. */ }
    if (saved) { attempt.current = saved;setUnknown(true);setMode('create'); }
    setReady(true);
    function restoreDraft(owner:string|null){draftOwner.current=owner;if(!saved&&!initialIdea&&!edited.current){try{const draft=readCreationDraft(sessionStorage,owner);if(draft){setTitle(draft.title);setBrief(draft.brief);setDraftRestored(Boolean(draft.title||draft.brief));}}catch{}}setDraftReady(true);}
    const controller = new AbortController();
    void projectRequest<Session>('/session', { signal: controller.signal }).then(value => { if (!controller.signal.aborted) {setExecutionMode(value.capabilities?.execution_mode ?? null);setRequiresSignIn(false);restoreDraft(value.principal.id);if(saved){if(saved.owner===value.principal.id){setTitle(saved.input.title??'');setBrief(saved.input.brief);}else{setAccountBlocked(true);setError(saved.owner?'Sign in with the account that started this saved creation.':'This older receipt has no account binding. Review saved Projects before continuing; it cannot be safely replayed.');}}} }).catch(reason => { if (!controller.signal.aborted && reason instanceof ProjectAPIError && reason.status === 401) {setRequiresSignIn(true);restoreDraft(null);} });
    return () => controller.abort();
  }, []);
  useEffect(()=>{if(draftReady&&draftOwner.current!==undefined&&!attempt.current){try{saveCreationDraft(sessionStorage,{title,brief,owner:draftOwner.current});}catch{}}},[title,brief,draftReady]);
  function forgetReceipt() { attempt.current = null; try { sessionStorage.removeItem(ATTEMPT_STORAGE); } catch { /* memory receipt still works */ } }
  async function create() {
    if (busy.current || !ready) return;
    const input = createInput(title, brief);
    if (!input&&!attempt.current) { setInvalid(true);setError('Use an optional title of up to 100 characters and a brief of 20–10,000 characters.'); briefRef.current?.focus(); return; }
    if (attempt.current && Date.now() - attempt.current.started >= 24 * 60 * 60 * 1000) { setError('This unresolved creation is older than the 24-hour recovery window. Check your saved Projects before starting another brief.'); return; }
    busy.current = true; setPending(true); setError('');setInvalid(false);
    try {
      const session=await projectRequest<Session>('/session');
      if(attempt.current&&(!attempt.current.owner||attempt.current.owner!==session.principal.id)){setAccountBlocked(true);throw new ProjectAPIError('CREATION_ACCOUNT_CHANGED',409);}
      const command=attempt.current??{key:crypto.randomUUID(),input:input!,started:Date.now(),owner:session.principal.id};
      attempt.current=command;
      try { sessionStorage.setItem(ATTEMPT_STORAGE, JSON.stringify(command)); } catch { /* Keep the receipt in memory when storage is blocked. */ }
      const result = await projectRequest<Created>('/projects', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': command.key,'X-F01-Expected-Owner':command.owner! }, body: JSON.stringify(command.input) });
      const target = creationTarget(result);
      if (!target) throw new ProjectAPIError('SERVICE_UNAVAILABLE', 0);
      forgetReceipt(); setUnknown(false);try{saveCreationDraft(sessionStorage,null);}catch{}
      router.push(target);
    } catch (reason) {
      if(reason instanceof ProjectAPIError&&reason.status===401)setRequiresSignIn(true);
      const unresolved = Boolean(attempt.current)&&(!(reason instanceof ProjectAPIError) || reason.code==='CREATION_ACCOUNT_CHANGED' || outcomeIsUnknown(reason.status, reason.code) || reason.code === 'IDEMPOTENCY_KEY_REUSED');
      setUnknown(unresolved); if (!unresolved) forgetReceipt();
      setError(reason instanceof Error ? reason.message : 'Creation could not be confirmed. Retry the same brief safely.');
      busy.current = false; setPending(false);
    }
  }
  const locked = pending || unknown;
  return <>
    {mode === 'plan' ? <><button className="button button-quiet" onClick={()=>setMode('create')}>← Back to project creation</button><ProjectPlanningForm initialIdea={brief} companion={<aside className="planning-guide"><h2>Explore a direction.</h2><p>This draft stays on this page. Return to project creation when you want to save, build and keep history.</p></aside>}/></> : <div className="planning-composition project-creation-composition">
      <form className="project-form saved-project-form" onSubmit={event=>{event.preventDefault();void create();}} noValidate aria-busy={pending}>
        {draftRestored&&<p className="restored-draft" role="status">Your draft is back. Review it before creating your project.</p>}
        <div className="brief-label"><label htmlFor="saved-project-brief">Product brief</label><ProjectPulse state={pending?'thinking':'idle'} label={pending?'Saving your project':unknown?'Save needs confirmation':'Step 1 of 6 · Describe'}/></div>
        <textarea ref={briefRef} id="saved-project-brief" name="brief" rows={6} value={brief} readOnly={locked} onChange={event=>{edited.current=true;setBrief(event.target.value);setInvalid(false);}} placeholder="For example: a leads dashboard for my property agency, with notes and a priority filter." aria-required="true" aria-invalid={invalid} aria-describedby="saved-brief-help creation-boundary"/>
        <div className="brief-support"><p id="saved-brief-help">Who is it for? What should they be able to do?</p><span className="meta">{Array.from(brief).length.toLocaleString('en-US')} / 10,000</span></div>
        <details className="creation-title-details"><summary>Project name (optional)</summary><label className="create-title-label" htmlFor="new-project-title">Project title <span>Optional</span></label><input id="new-project-title" name="title" value={title} readOnly={locked} onChange={event=>{edited.current=true;setTitle(event.target.value);setInvalid(false);}} placeholder="A name you will recognize later"/></details>
        {unknown&&<div className="unresolved-creation" role="status">The save has not been confirmed. Retry checks the same command and recovers its result. Your brief stays locked until the result is known.</div>}
        {error&&<p className="form-error" role="alert">{error}</p>}
        <div className="planning-actions">{accountBlocked?<Link className="button button-primary" href="/account">Review the account for this saved command</Link>:requiresSignIn?<Link className="button button-primary" href="/sign-in?returnTo=%2Fprojects%2Fnew">Sign in to create your project</Link>:<button className="button button-primary" disabled={pending||!ready}>{pending?'Saving project…':unknown?'Retry project creation':executionMode==='simulated'?'Create demo project':'Create project'}</button>}</div>
        <p className="composer-note" id="creation-boundary">{executionMode==='simulated'?<>Demo mode saves your project and runs a labeled sample.</>:<>Next: make a plan and approve it. Creating the project starts no build or deployment.</>}</p>
        <details className="creation-extras"><summary>Explore a draft without saving a project</summary><p>A draft plan is optional. It stays on this page and cannot be built until you create a saved project.</p><button type="button" className="button button-secondary" disabled={locked} onClick={()=>setMode('plan')}>Explore a draft plan</button></details>
      </form>
      <aside className="creation-companion"><h2>Start with the essentials.</h2><p>Plain language is enough. Describe the outcome; the plan will turn it into specific work.</p><ProjectStarters selected={projectStarters.find(item=>item.brief===brief)?.id} disabled={locked} onSelect={id=>{edited.current=true;setBrief(projectStarters.find(item=>item.id===id)!.brief);setError('');briefRef.current?.focus();}}/><div className="creation-path"><span className="meta">WHAT HAPPENS NEXT</span><ol><li><strong>Plan</strong><span>Review the proposed work.</span></li><li><strong>Approve & build</strong><span>Follow real, saved progress.</span></li><li><strong>Preview & publish</strong><span>Try it before it goes live.</span></li></ol></div></aside>
    </div>}
  </>;
}
