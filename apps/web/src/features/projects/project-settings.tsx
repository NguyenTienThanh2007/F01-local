'use client';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { projectRequest, ProjectAPIError } from '@/lib/projects/browser';
import { projectETag, type Project, type UpdateInput } from '@/lib/projects/contracts';

export function ProjectSettings({ project, onSaved }: { project: Project; onSaved: (project: Project) => void }) {
  const [title, setTitle] = useState(project.title);
  const [pending, setPending] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [latest, setLatest] = useState(project), [conflict, setConflict] = useState(false);
  const busy = useRef(false);
  const displayed = project.metadata_version > latest.metadata_version ? project : latest;
  const active = ['understanding','planning','building','verifying','deploying'].includes(project.lifecycle);
  useEffect(() => { if (project.metadata_version > latest.metadata_version) { setConflict(true); setError('This project changed elsewhere. Your title draft is preserved. Review the latest metadata before saving.'); } }, [project.metadata_version,latest.metadata_version]);
  async function save(update: UpdateInput) {
    if (busy.current || conflict || ('archived' in update && active)) return;
    if ('title' in update && (!title.trim() || Array.from(title.trim()).length > 100)) { setError('Use a title of 1–100 characters.'); return; }
    busy.current = true; setPending(true); setError(''); setNotice('');
    try {
      const saved = await projectRequest<Project>(`/projects/${project.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'If-Match': projectETag(latest) }, body: JSON.stringify(update) });
      setLatest(saved); setConflict(false); setTitle(saved.title); setNotice('Project settings saved.'); onSaved(saved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to save settings.');
      if (reason instanceof ProjectAPIError && reason.status === 412) setConflict(true);
    } finally { busy.current = false; setPending(false); }
  }
  async function review() {
    if (busy.current) return;
    busy.current = true; setPending(true); setError('');
    try { const saved = await projectRequest<Project>(`/projects/${project.id}`); setLatest(saved); setConflict(false); setNotice(`Latest title: ${saved.title}. ${saved.archived_at ? 'Archived' : 'Active'}. Your title draft is preserved; review it before saving.`); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to refresh project.'); }
    finally { busy.current = false; setPending(false); }
  }
  return <section className="project-settings" aria-label={`Settings for ${project.title}`} aria-busy={pending}>
    <form onSubmit={event => { event.preventDefault(); void save({ title: title.trim() }); }}>
      <label htmlFor={`title-${project.id}`}>Project title</label><div className="rename-line"><input id={`title-${project.id}`} value={title} onChange={event => setTitle(event.target.value)} readOnly={pending} aria-invalid={Boolean(error && (!title.trim() || Array.from(title.trim()).length > 100))} /><button className="button button-secondary" disabled={pending || conflict}>{pending ? 'Saving…' : 'Save title'}</button></div>
    </form>
    {conflict && <div className="metadata-review"><p>Current title: <strong>{displayed.title}</strong> · {displayed.archived_at ? 'Archived' : 'Active'}</p><button className="button button-secondary" disabled={pending} onClick={() => void review()}>Review latest metadata</button></div>}
    <div className="archive-line"><div><p>{displayed.archived_at ? 'Keep this project in your active workspace again.' : 'Archive hides this project from the active list and preserves its history.'}</p>{active && <p id={`archive-reason-${project.id}`}>A queued or running simulation must end before archiving. <Link className="text-action" href={`/projects/${project.id}?panel=run`}>Inspect or cancel the simulation ↗</Link></p>}</div><button className="button button-secondary" disabled={pending || conflict || active} aria-describedby={active ? `archive-reason-${project.id}` : undefined} onClick={() => void save({ archived: !latest.archived_at })}>{displayed.archived_at ? 'Unarchive project' : 'Archive project'}</button></div>
    {error && <p className="form-error" role="alert">{error}</p>}{notice && <p role="status" className="settings-notice">{notice}</p>}
  </section>;
}
