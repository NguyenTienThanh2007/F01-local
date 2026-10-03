'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ProjectPulse } from '@/features/project-pulse/project-pulse';
import { projectStarters } from '@/features/project-planning/project-starters';
import { projectRequest } from '@/lib/projects/browser';
import { stateNames, states, type ProjectList, type Project, type Session } from '@/lib/projects/contracts';
import { ProjectSettings } from './project-settings';

export function ProjectDashboard({ q, status, archived, cursor }: { q: string; status: string; archived: boolean; cursor: string }) {
  const [data, setData] = useState<ProjectList | null>(null), [error, setError] = useState(''), [loading, setLoading] = useState(true), [refresh, setRefresh] = useState(0), [selected, setSelected] = useState<string | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const params = new URLSearchParams({ q, status, archived: String(archived) }); if (cursor) params.set('cursor', cursor);
  const query = params.toString();
  useEffect(() => { const controller = new AbortController(); projectRequest<Session>('/session', { signal: controller.signal }).then(setSession).catch(() => {}); return () => controller.abort(); }, []);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    projectRequest<ProjectList>(`/projects?${query}`, { signal: controller.signal }).then(result => { if (!controller.signal.aborted) setData(result); }).catch(reason => { if (!controller.signal.aborted) setError(reason.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [query, refresh]);
  function saved(project: Project) { setData(old => old ? { ...old, items: old.items.filter(item => item.id !== project.id || Boolean(project.archived_at) === archived).map(item => item.id === project.id ? project : item) } : old); setRefresh(n => n + 1); }
  function nextURL(cursor: string) { const next = new URLSearchParams(params); next.set('cursor', cursor); return `/projects?${next}`; }
  const filtered = Boolean(q || status || archived || cursor);
  return <div className="page dashboard persisted-dashboard">
    <div className="page-eyebrow"><span>YOUR WORKSPACE / PROJECTS</span><span>{session ? `${session.principal.identity_mode.toUpperCase()} IDENTITY` : 'WORKSPACE ACCESS'}</span></div>
    <div className="page-heading"><div><h1>A home for what’s next.</h1><p className="muted">Your software. Its context. The next version of it.</p></div><Link href="/projects/new" className="button button-primary">New project <span aria-hidden="true">↗</span></Link></div>
    <form className="workspace-toolbar project-filters" action="/projects" method="get">
      <span className="workspace-tab">Projects<span className="tab-rule" /></span><div className="workspace-search"><label className="sr-only" htmlFor="project-search">Search projects</label><input id="project-search" name="q" type="search" defaultValue={q} placeholder="Search project titles" maxLength={100} /></div>
      <label className="sr-only" htmlFor="project-filter">Project state</label><select id="project-filter" name="status" defaultValue={status}><option value="">All states</option>{states.map(state => <option key={state} value={state}>{stateNames[state]}</option>)}</select>
      <label className="sr-only" htmlFor="archive-filter">Archive filter</label><select id="archive-filter" name="archived" defaultValue={String(archived)}><option value="false">Active projects</option><option value="true">Archived projects</option></select><button className="button button-secondary">Apply filters</button>
    </form>
    <div className="project-list-state" role="status">{loading ? 'Loading saved projects…' : error ? 'Project connection unavailable' : `${data?.items.length ?? 0} projects on this page${archived ? ' · Archived' : ''}`}</div>
    {error && <div className="project-connection-error"><p className="form-error" role="alert">{error}</p><Link className="button button-secondary" href="/account">Review account access</Link><button className="button button-secondary" disabled={loading} onClick={() => setRefresh(n => n + 1)}>Retry project list</button></div>}
    {loading && !data && <div className="project-skeletons" aria-hidden="true">{[0, 1, 2].map(n => <div key={n}><span /><i /></div>)}</div>}
    <section className="project-register" aria-label="Saved projects" aria-busy={loading}>{data?.items.map((project, index) => <article className={`saved-project ${selected === project.id ? 'selected-project' : ''}`} key={project.id}>
      <div className="saved-project-row"><span className="project-index meta">{String(index + 1).padStart(2, '0')}</span><div className="project-identity"><Link href={`/projects/${project.id}`} className="saved-project-title">{project.title}<span aria-hidden="true">↗</span></Link><span className="meta">{project.archived_at ? 'ARCHIVED / ' : ''}PROJECT {project.id.slice(0, 8).toUpperCase()}</span></div><ProjectPulse state={project.lifecycle} label={stateNames[project.lifecycle]} /><div className="project-time"><span>Last activity</span><time dateTime={project.last_activity_at}>{new Date(project.last_activity_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time></div><button className="button button-quiet" aria-expanded={selected === project.id} aria-controls={`settings-${project.id}`} onClick={() => setSelected(selected === project.id ? null : project.id)}>{selected === project.id ? 'Close settings' : 'Project settings'}</button></div>
      {selected === project.id && <div id={`settings-${project.id}`}><ProjectSettings project={project} onSaved={saved} /></div>}
    </article>)}</section>
    {!loading && !error && data?.items.length === 0 && <section className="workspace-empty" aria-labelledby="empty-title"><div className="empty-register" aria-hidden="true"><div className="register-top"><span>PROJECT / —</span><span>FIRST EDITION</span></div><div className="register-strokes"><i /><i /><i /></div><div className="register-line" /><div className="register-line register-short" /><span className="register-bottom">A PLACE TO BEGIN</span></div><div className="empty-copy"><span className="meta">{filtered ? 'REFINE YOUR VIEW' : 'THE NEXT THING STARTS HERE'}</span><h2 id="empty-title">{filtered ? 'No projects in this view.' : <>Give your idea<br />a working direction.</>}</h2><p>{filtered ? 'Try another title or state, or return to your active projects.' : 'Start with a title and a brief. Your project and original request stay in your workspace.'}</p>{filtered ? <Link href="/projects" className="empty-action">Clear filters ↗</Link> : <Link href="/projects/new" className="empty-action">Create your first project ↗</Link>}<ProjectPulse state="idle" label="Ready when you are" /></div></section>}
    {data?.next_cursor && <div className="project-pagination"><Link className="button button-secondary" href={nextURL(data.next_cursor)}>Next page</Link><Link href="/projects">First page / reset filters</Link></div>}
    <section className="starter-shelf" aria-labelledby="starters-title"><div className="direction-heading"><h2 id="starters-title">A few good starting points.</h2><span className="meta">STARTER BRIEFS / NOT SAVED PROJECTS</span></div><div className="starter-artifacts">{projectStarters.map(item => <Link href={`/projects/new?starter=${item.id}`} key={item.id} className={`starter-artifact artifact-${item.id}`}><div className="artifact-visual" aria-hidden="true">{item.id === 'crm' ? <><div className="artifact-bars"><i /><i /><i /></div><span>PIPELINE / 01</span></> : item.id === 'booking' ? <><span className="artifact-date">12</span><div className="artifact-agenda"><i /><i /><i /></div></> : <><span className="artifact-path" /><span className="artifact-game-dot" /><span className="artifact-game-target">×</span></>}</div><div className="artifact-description"><span className="meta">{item.number} / {item.category}</span><h3>{item.title}<span aria-hidden="true">↗</span></h3><p>Use this brief as a starting point. Make it your own.</p></div></Link>)}</div></section>
    <footer className="page-footer"><span>CREATE → RUN → MANAGE → EVOLVE</span><span>{!session?.capabilities ? 'Saved projects use the project service.' : session.capabilities.simulation_runner ? 'Simulation demonstrations are available inside saved projects.' : 'Projects saved. Simulation progression is paused.'}</span></footer>
  </div>;
}
