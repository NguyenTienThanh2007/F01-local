'use client';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { createContext, useContext, useEffect, useState, useCallback, useRef, useId, useLayoutEffect, type ReactNode } from 'react';
import { ProjectPulse } from '@/features/project-pulse/project-pulse';
import { containDialogFocus } from '@/components/ui/dialog-focus';
import { projectRequest } from '@/lib/projects/browser';
import { stateNames, type Session } from '@/lib/projects/contracts';
import { uuid, type Snapshot } from '@/lib/workspace/contracts';
import type { BuildEvent } from '@/lib/workspace/trace';
import { useBuildFeed, type Transport } from './feed';
import { useRunCommands } from './run-commands';
import { BuildTrace, RunDetails, DeploymentDetails } from './trace';
import { SourceInspector } from './real-build';
import { RequestDrawer } from './requests';
type Context = { historyReady: boolean; events: BuildEvent[]; transport: Transport; inspectedRunId: string | null; setInspectedRunId: (id: string | null) => void; runCommands: ReturnType<typeof useRunCommands>; id: string; snapshot: Snapshot; refresh: (quiet?: boolean, resources?: boolean) => Promise<Snapshot | null>; generation: number; openRequests: () => void; viewport: 'desktop' | 'tablet' | 'phone'; setViewport: (value: 'desktop' | 'tablet' | 'phone') => void; setInspectedVersion: (value: number | null) => void };
const WorkspaceContext = createContext<Context | null>(null);
export function useWorkspace() { const value = useContext(WorkspaceContext); if (!value) throw new Error('Workspace context missing'); return value; }
export function useResource<T>(path: string | null) {
  const { generation } = useWorkspace();
  const [state, setState] = useState<{ path: string | null; data: T | null; error: string; pending: boolean }>({ path, data: null, error: '', pending: Boolean(path) });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { if (!path) { setState({ path, data: null, error: '', pending: false }); return; } const controller = new AbortController();
    setState(previous => ({ path, data: previous.path === path ? previous.data : null, error: '', pending: true }));
    projectRequest<T>(path, { signal: controller.signal }).then(data => { if (!controller.signal.aborted) setState({ path, data, error: '', pending: false }); }).catch(e => { if (!controller.signal.aborted) setState(previous => ({ ...previous, error: e.message, pending: false })); });
    return () => controller.abort();
  }, [path, generation, attempt]);
  const selected = state.path === path ? state : { data: null, error: '', pending: Boolean(path) };
  const retry = useCallback(() => setAttempt(n => n + 1), []);
  return { ...selected, retry };
}
export function ResourceState({ pending, error, retry }: { pending: boolean; error: string; retry: () => void }) { return <>{pending && <p className="resource-loading" role="status">Loading saved records…</p>}{error && <div className="workspace-notice"><p role="alert">{error}</p><button className="button button-secondary" onClick={retry}>Retry records</button></div>}</>; }
const sections = [['', 'Preview'], ['/brief', 'Brief'], ['/brain', 'Brain'], ['/planning', 'Planning'], ['/activity', 'Activity'], ['/versions', 'Versions'], ['/settings', 'Settings']] as const;
const utilities = ['trace', 'run', 'files', 'logs', 'deployment', 'runtime'] as const;
type Panel = typeof utilities[number] | 'requests' | null;
export function Workspace({ id, children }: { id: string; children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null), [error, setError] = useState(''), [pending, setPending] = useState(true), [generation, setGeneration] = useState(0);
  const [panel, setPanel] = useState<Panel>(null), [desktop, setDesktop] = useState(false);
  const [inspectedRunId, setInspectedRunId] = useState<string | null>(null);
  const snapshotRef = useRef<Snapshot | null>(null);
  const [inspectedVersion, setInspectedVersion] = useState<number | null>(null);
  const [viewport, setViewport] = useState<'desktop' | 'tablet' | 'phone'>('desktop');
  const pathname = usePathname(), query = useSearchParams();
  const refresh = useCallback(async (quiet = false, resources = true) => {
    if (!quiet) setPending(true);
    try {
      const data = await projectRequest<Snapshot>(`/projects/${id}/workspace`);
      if (!snapshotRef.current || data.last_sequence >= snapshotRef.current.last_sequence) { snapshotRef.current = data; setSnapshot(data); }
      setError(''); if (resources) setGeneration(n => n + 1); return snapshotRef.current;
    } catch (e) { setError(e instanceof Error ? e.message : 'Project unavailable.'); return null; }
    finally { if (!quiet) setPending(false); }
  }, [id]);
  const onEvents = useCallback((batch: BuildEvent[]) => {
    const relevant = batch.some(event => ['release.packaging_queued','release.package_verified','release.target_queued','release.queued','release.succeeded','release.failed','release.canceled','execution.context_resolution','execution.generated','execution.materialization','execution.install','execution.typecheck','execution.build','execution.test','execution.verification','execution.preview_ready','execution.failed','execution.canceled','execution.queued','run.phase_changed','run.queued','run.succeeded','run.failed','run.canceled','request.recorded','project.renamed','project.archived','project.unarchived'].includes(event.type));
    const resources = batch.some(event => ['release.packaging_queued','release.package_verified','release.target_queued','release.queued','release.succeeded','release.failed','release.canceled','execution.preview_ready','execution.failed','execution.canceled','run.queued','run.succeeded','run.failed','run.canceled','request.recorded','project.renamed','project.archived','project.unarchived'].includes(event.type));
    if (relevant) void refresh(true,resources);
  }, [refresh]);
  const feed = useBuildFeed(id,snapshot,onEvents);
  const runCommands = useRunCommands(id,refresh);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { const controller = new AbortController(); void projectRequest<Session>('/session', { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setSession(value); }).catch(() => {}); return () => controller.abort(); }, []);
  useEffect(() => { const media = matchMedia('(min-width: 1280px)'); const update = () => setDesktop(media.matches); update(); media.addEventListener('change', update); return () => media.removeEventListener('change', update); }, []);
  const requestedPanel = query.get('panel');
  useEffect(() => { if (requestedPanel === 'requests' || utilities.includes(requestedPanel as typeof utilities[number])) setPanel(requestedPanel as Panel); }, [requestedPanel]);
  const requestedRun = query.get('run');
  useEffect(() => { setInspectedRunId(requestedRun && uuid.test(requestedRun) ? requestedRun : null); }, [requestedRun]);
  if (!snapshot) return <div className="page workspace-loading"><Link href="/projects" className="back-link">← Projects</Link>{pending ? <><h1>Opening your project</h1><div className="workspace-skeleton" aria-hidden="true" /><p role="status">Loading saved workspace…</p></> : <><h1>This project is unavailable.</h1><p role="alert">{error}</p><button className="button button-secondary" onClick={() => void refresh()}>Retry workspace</button></>}</div>;
  const project = snapshot.project;
  const real = session?.capabilities?.execution_mode === 'real' || (snapshot.active_run ?? snapshot.latest_run)?.mode === 'real' || snapshot.current_version?.mode === 'real';
  const inspector = <div className="workspace-inspector-content">
    <div className="inspector-switches" role="group" aria-label="Inspector views">{utilities.map(name => <button key={name} aria-pressed={panel === name} onClick={() => setPanel(name)}>{name === 'trace' ? 'Build Trace' : name === 'run' ? 'Run details' : name[0]!.toUpperCase() + name.slice(1)}</button>)}<button aria-pressed={panel === 'requests'} onClick={() => setPanel('requests')}>Requests</button></div>
    <div hidden={panel !== 'requests'}><RequestDrawer /></div>
    <div hidden={panel === 'requests'} className="inspector-body">
      <div hidden={panel !== 'trace'}><BuildTrace /></div>
      <div hidden={panel !== 'run'}><RunDetails /></div>
      <div hidden={panel !== 'deployment'}><DeploymentDetails /></div>
      {panel === 'files' && <SourceInspector/>}
      {panel !== 'trace' && panel !== 'run' && panel !== 'deployment' && panel !== 'files' && <><span className="meta">CAPABILITY / NOT AVAILABLE</span><h2>{panel ? panel[0]!.toUpperCase() + panel.slice(1) : 'Inspector'}</h2><p>{panel === 'logs' ? 'Build Trace contains sanitized structured evidence. Unrestricted terminal output is unavailable.' : 'Preview runtimes are isolated and expire automatically. Production runtime controls are unavailable.'}</p></>}

    </div>
  </div>;
  return <WorkspaceContext.Provider value={{ historyReady: feed.historyReady, events: feed.events, transport: feed.transport, inspectedRunId, setInspectedRunId, runCommands, id, snapshot, refresh, generation, openRequests: () => setPanel('requests'), viewport, setViewport, setInspectedVersion }}><div className="workspace-page">
    <header className="project-header"><div className="project-heading"><Link className="meta" href="/projects">PROJECTS / SAVED WORKSPACE</Link><h1>{project.title}</h1></div><div className="project-state"><span role="status" aria-live="polite" aria-atomic="true"><ProjectPulse state={project.lifecycle} label={real && project.lifecycle === 'live' ? 'Preview ready' : stateNames[project.lifecycle]} /></span><span className="mode-label">{real ? 'Application build' : session ? 'Demo mode' : 'Saved project'}</span>{snapshot.active_run && <span className="meta">{snapshot.active_run.status === 'queued' ? 'Queued · not started' : stateNames[snapshot.active_run.phase ?? 'understanding']}</span>}{(inspectedVersion ?? snapshot.current_version?.number) && <span className="meta">{inspectedVersion && inspectedVersion !== snapshot.current_version?.number ? 'Historical' : 'Current'} {snapshot.current_version?.mode === 'real' ? 'version' : 'demo version'} {inspectedVersion ?? snapshot.current_version?.number}</span>}{project.archived_at && <span className="meta">Archived</span>}</div></header>
    <div className="workspace-navigation"><nav aria-label="Project navigation">{sections.map(([suffix, label]) => <Link key={label} href={`/projects/${id}${suffix}`} aria-current={pathname === `/projects/${id}${suffix}` ? 'page' : undefined}>{label}</Link>)}</nav><div className="workspace-tools"><button className="button button-quiet" aria-expanded={panel === 'requests'} onClick={() => setPanel(panel === 'requests' ? null : 'requests')}>Requests</button><button className="button button-secondary" aria-expanded={panel !== null && panel !== 'requests'} onClick={() => setPanel(panel && panel !== 'requests' ? null : 'trace')}>Inspect work</button></div></div>
    <div className="workspace-sync"><span>{pending ? 'Refreshing saved context…' : `Brain revision ${snapshot.current_brain.revision} · ${snapshot.current_version ? `Current ${snapshot.current_version.mode === 'real' ? '' : 'demo '}version ${snapshot.current_version.number}` : 'No completed version'} · Saved sequence ${snapshot.last_sequence}`}</span><button onClick={() => void refresh()} disabled={pending}>Refresh context</button></div>
    {feed.transport !== 'live' && <div className="workspace-connection" role="status"><span>{feed.transport === 'offline' ? 'Offline · saved context remains visible. Reconnecting automatically.' : feed.transport === 'polling' ? 'Streaming unavailable · checking saved events by polling.' : feed.transport === 'connecting' ? 'Connecting to saved events…' : feed.transport === 'session expired' ? 'Workspace access expired. Saved content has not been changed.' : 'Project access is unavailable. No new project data will be loaded.'}</span>{['polling','offline'].includes(feed.transport) && <button className="button button-quiet" onClick={feed.retry}>Retry connection</button>}{feed.transport === 'session expired' && <Link href="/sign-in" className="text-action">Review workspace access ↗</Link>}</div>}
    {error && <p role="alert" className="form-error workspace-refresh-error">{error} Your last loaded context remains visible.</p>}
    {(runCommands.error || runCommands.notice || runCommands.recovery) && <div className="workspace-notice run-command-status" aria-label="Simulation command result">{runCommands.error && <p role="alert">{runCommands.error}</p>}{runCommands.notice && <p role="status">{runCommands.notice}</p>}{runCommands.recovery && <><p>Simulation command awaiting confirmation. Its exact key and input context are retained.</p><button className="button button-secondary" disabled={runCommands.pending} onClick={() => void runCommands.resume()}>{runCommands.pending ? 'Confirming simulation…' : 'Resolve saved simulation command'}</button></>}</div>}
    <div className={`workspace-body ${desktop && panel ? 'with-inspector' : ''}`}><div className="workspace-canvas">{children}</div><WorkspacePanel open={panel !== null} desktop={desktop} onClose={() => setPanel(null)} title={panel === 'requests' ? 'Requests' : 'Utility inspector'}>{inspector}</WorkspacePanel></div>
  </div></WorkspaceContext.Provider>;
}
export function time(value: string) { return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); }

function WorkspacePanel({ open, desktop, onClose, title, children }: { open: boolean; desktop: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null), returnFocus = useRef<HTMLElement | null>(null), previousDesktop = useRef(desktop); const titleId = useId();
  useLayoutEffect(() => { const dialog = ref.current; if (!dialog) return;
    if (dialog.open && previousDesktop.current !== desktop) dialog.close();
    previousDesktop.current = desktop;
    if (open && !dialog.open) { if (!returnFocus.current) returnFocus.current = document.activeElement as HTMLElement; if (desktop) dialog.show(); else dialog.showModal(); }
    if (!open && dialog.open) { dialog.close(); returnFocus.current?.focus(); returnFocus.current = null; }
  }, [open, desktop]);
  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open || !desktop) return;
    const size = () => dialog.style.setProperty('--inspector-available-height', `${Math.max(300, innerHeight - Math.max(16, dialog.getBoundingClientRect().top) - 16)}px`);
    size(); window.addEventListener('resize', size); window.addEventListener('scroll', size, { passive: true });
    return () => { window.removeEventListener('resize', size); window.removeEventListener('scroll', size); };
  }, [open, desktop, children]);
  useEffect(() => () => { ref.current?.close(); }, []);
  return <dialog ref={ref} tabIndex={-1} className={desktop ? 'workspace-inspector desktop-panel' : 'sheet workspace-panel'} aria-labelledby={titleId} onCancel={e => { e.preventDefault(); onClose(); }} onKeyDown={e => { containDialogFocus(e); if (e.key === 'Escape') { e.preventDefault(); onClose(); } }} onClick={e => { if (!desktop && e.target === ref.current) onClose(); }}><div className="inspector-heading"><h2 id={titleId}>{title}</h2><button className="icon-button" aria-label="Close inspector" onClick={onClose}>×</button></div>{children}</dialog>;
}
