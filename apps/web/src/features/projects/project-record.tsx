'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ProjectPulse } from '@/features/project-pulse/project-pulse';
import { projectRequest, ProjectAPIError } from '@/lib/projects/browser';
import { stateNames, type Project } from '@/lib/projects/contracts';
import { ProjectSettings } from './project-settings';
export function ProjectRecord({ id }: { id: string }) {
  const [project, setProject] = useState<Project | null>(null), [error, setError] = useState(''), [missing, setMissing] = useState(false), [loading, setLoading] = useState(true), [retry, setRetry] = useState(0);
  useEffect(() => { const controller = new AbortController(); setLoading(true); setError('');
    projectRequest<Project>(`/projects/${id}`, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setProject(value); }).catch(reason => { if (!controller.signal.aborted) { setError(reason.message); setMissing(reason instanceof ProjectAPIError && reason.status === 404); } }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort();
  }, [id, retry]);
  return <div className="page project-record"><Link href="/projects" className="back-link">← Workspace / Projects</Link><div className="page-eyebrow"><span>PROJECT / SAVED RECORD</span><span>DEVELOPMENT IDENTITY</span></div>{loading && <p role="status">Loading saved project…</p>}{error && <div><h1>{missing ? 'This project is unavailable.' : 'Unable to load project.'}</h1><p role="alert" className="form-error">{error}</p>{!missing && <button className="button button-secondary" onClick={() => setRetry(n => n + 1)}>Retry project</button>}</div>}{project && <><div className="page-heading"><div><h1>{project.title}</h1><p className="muted">{project.archived_at ? 'Archived project · history preserved' : 'Saved in your workspace'}</p></div><ProjectPulse state={project.lifecycle} label={stateNames[project.lifecycle]} /></div><dl className="project-record-facts"><div><dt>Project ID</dt><dd>{project.id}</dd></div><div><dt>Created</dt><dd><time dateTime={project.created_at}>{new Date(project.created_at).toLocaleString()}</time></dd></div><div><dt>Last activity</dt><dd><time dateTime={project.last_activity_at}>{new Date(project.last_activity_at).toLocaleString()}</time></dd></div></dl><div className="record-boundary"><span className="meta">DEMO PROJECT / PERSISTED</span><h2>A foundation for what comes next.</h2><p>Your original brief and initial context were saved. Workspace and Brain viewing are coming next. Creation queues an initial demonstration; execution and previews are not available yet.</p></div><h2 className="settings-heading">Project settings</h2><ProjectSettings project={project} onSaved={setProject} /></>}</div>;
}
