'use client';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { issueRelationships, phases, type BuildEvent } from '@/lib/workspace/trace';
import type { Deployments, Run, Runs } from '@/lib/workspace/contracts';
import { useWorkspace, useResource, ResourceState, time } from './workspace';
const labels = {understanding:'Understanding',planning:'Planning',building:'Building',verifying:'Verifying',deploying:'Deploying',outcome:'Live / Needs attention'};
function groups(events: BuildEvent[]) {
  const result: {phase: keyof typeof labels; events: BuildEvent[]}[] = [];
  for (const event of events) {
    const phase = ['run.succeeded','run.failed','run.canceled'].includes(event.type) ? 'outcome' : event.phase ?? 'understanding';
    if (result.at(-1)?.phase !== phase) result.push({phase,events:[]});
    result.at(-1)!.events.push(event);
  }
  return result;
}
export function BuildTrace() {
  const { snapshot, events, transport, historyReady, inspectedRunId } = useWorkspace();
  const runId = inspectedRunId ?? snapshot.latest_run?.id;
  const selected = events.filter(event => event.run_id === runId);
  const [follow,setFollow] = useState(true), [seen,setSeen] = useState(0);
  const scroll = useRef<HTMLDivElement>(null);
  useEffect(() => { setFollow(true); setSeen(0); },[runId]);
  useEffect(() => { if (follow && scroll.current) { scroll.current.scrollTop = scroll.current.scrollHeight; setSeen(selected.length); } },[selected.length,follow]);
  useEffect(() => {
    const element = scroll.current; if (!element || !follow) return;
    const observer = new ResizeObserver(() => { element.scrollTop = element.scrollHeight; });
    observer.observe(element); return () => observer.disconnect();
  }, [follow]);
  const related = issueRelationships(selected);
  const unread = Math.max(0,selected.length - seen);
  function inspectEvent(eventId: string) { setFollow(false); const target = document.getElementById(`trace-${eventId}`); target?.focus({ preventScroll: true }); target?.scrollIntoView({ block: 'nearest' }); }
  return <section className="build-trace" aria-label="Build Trace">
    <span className="meta">BUILD TRACE / SAVED EXECUTION</span><h2>Saved execution timeline</h2>
    <details className="trace-context" onToggle={event => { if (event.currentTarget.open) setFollow(false); }}><summary>Simulation scope and local times</summary><p className="record-disclosure">Simulation events remain labeled. Real runs record observed command phases and verified source provenance.</p><p className="trace-timezone">Times: {Intl.DateTimeFormat().resolvedOptions().timeZone} · 24-hour clock. UTC is available in event references.</p></details>
    <p className="trace-transport" data-transport={transport}>Event connection: {transport}{transport === 'session expired' && <> · <Link href="/sign-in">Review workspace access</Link></>}</p>
    {!historyReady && <p className="record-disclosure" role="status">Loading earlier saved events. Recent snapshot events remain available.</p>}
    <ol className="trace-phase-index" aria-label="Build Trace phases">{[...phases,'outcome' as const].map(phase => <li key={phase}>{labels[phase]}</li>)}</ol>
    <div className="trace-follow"><button className="button button-quiet" aria-pressed={follow} onClick={() => { setFollow(value => !value); setSeen(selected.length); }}>{follow ? 'Pause following' : 'Follow latest'}</button>{!follow && <button className="button button-secondary" onClick={() => setFollow(true)}>Jump to latest{unread ? ` (${unread} new)` : ''}</button>}</div>
    <div ref={scroll} className="trace-scroll" tabIndex={0} aria-label="Ordered Build Trace" onScroll={() => {
      const element=scroll.current!; const atEnd=element.scrollHeight-element.clientHeight-element.scrollTop < 24;
      if (!atEnd) setFollow(false); else if (follow) setSeen(selected.length);
    }}>
      {!selected.length && <p>No saved events for this attempt.</p>}
      {groups(selected).map(group => <section className="trace-group" key={group.events[0]!.id} data-phase={group.phase}><h3>{labels[group.phase]}</h3><ol>{group.events.map(event => { const repair = related.find(pair => pair.issue.id === event.id)?.repairs[0]; const issue = related.find(pair => pair.issue.payload.issue_id === event.payload.resolves_issue_id)?.issue; return <li id={`trace-${event.id}`} tabIndex={-1} key={event.id} data-sequence={event.sequence} data-severity={event.severity}>
        <div className="trace-event-meta"><span>#{event.sequence} · {event.mode === 'simulated' ? 'Simulation' : event.mode === 'real' ? 'Real execution' : 'Saved action'}</span><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'})}</time></div><p>{event.message}</p>{event.payload.execution_phase && <span className="meta">{event.payload.execution_phase}</span>}
        {event.payload.issue_id && <div className="trace-issue"><strong>Issue: {event.payload.issue_id}</strong><p>{repair ? <a href={`#trace-${repair.id}`} onClick={e => { e.preventDefault(); inspectEvent(repair.id); }}>Linked fixture repair at sequence #{repair.sequence}</a> : 'No linked fixture repair recorded.'}</p></div>}
        {event.payload.resolves_issue_id && <p className="trace-issue">{issue ? <a href={`#trace-${issue.id}`} onClick={e => { e.preventDefault(); inspectEvent(issue.id); }}>Fixture repair → issue {event.payload.resolves_issue_id}</a> : <>Fixture repair → issue {event.payload.resolves_issue_id} · earlier history pending</>}</p>}
        <details className="trace-references"><summary>Event references · #{event.sequence}</summary><dl><dt>Event</dt><dd>{event.type}</dd><dt>Run</dt><dd>{event.run_id ?? 'None'}</dd><dt>Request</dt><dd>{event.request_id ?? 'None'}</dd><dt>UTC timestamp</dt><dd>{event.occurred_at}</dd><dt>Fixture cursor</dt><dd>{event.payload.step_cursor ?? 'Not a fixture step'}</dd></dl></details>
      </li>; })}</ol></section>)}
    </div>
  </section>;
}
export function RunDetails() {
  const { id,snapshot,inspectedRunId,setInspectedRunId,runCommands } = useWorkspace();
  const [cursor,setCursor] = useState('');
  const list=useResource<Runs>(`/projects/${id}/runs${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`);
  const detail=useResource<Run>(inspectedRunId ? `/projects/${id}/runs/${inspectedRunId}` : null);
  const run=inspectedRunId ? (snapshot.latest_run?.id === inspectedRunId ? snapshot.latest_run : detail.data) : snapshot.latest_run;
  const active=run?.status==='queued' || run?.status==='running';
  return <section className="run-details"><span className="meta">RUN DETAILS / {run?.mode === 'real' ? 'REAL EXECUTION' : 'SIMULATION'}</span><h2>{run ? `Attempt ${run.attempt} · ${run.status}` : 'No recorded run'}</h2>
    <p className="record-disclosure">{inspectedRunId && inspectedRunId !== snapshot.latest_run?.id ? 'Historical attempt · inspection only.' : 'Latest saved attempt.'}</p>
    <label htmlFor="run-selection">Inspect attempt</label><select id="run-selection" value={inspectedRunId ?? ''} onChange={e => setInspectedRunId(e.target.value || null)}><option value="">Latest attempt</option>{inspectedRunId && !list.data?.items.some(item => item.id===inspectedRunId) && <option value={inspectedRunId}>Selected historical attempt · {inspectedRunId.slice(0,8)}</option>}{list.data?.items.map(item => <option key={item.id} value={item.id}>Attempt {item.attempt} · {item.status} · {item.id.slice(0,8)}</option>)}</select>
    <ResourceState {...list} />{inspectedRunId && <ResourceState {...detail} />}
    <div className="record-pagination">{cursor && <button onClick={() => setCursor('')}>Latest attempts</button>}{list.data?.next_cursor && <button onClick={() => setCursor(list.data!.next_cursor!)}>Older attempts</button>}</div>
    {run && <><dl><dt>Run ID</dt><dd>{run.id}</dd><dt>Fixture</dt><dd>{run.scenario_id}@{run.scenario_version}</dd><dt>Phase</dt><dd>{run.phase ?? 'Queued'}</dd><dt>Request ID</dt><dd>{run.request_id}</dd><dt>Frozen Brain</dt><dd>{run.input_brain_revision_id}</dd><dt>Base version</dt><dd>{run.base_version_id ?? 'None'}</dd><dt>Retry of</dt><dd>{run.retry_of_run_id ?? 'First attempt'}</dd><dt>Persisted cursor</dt><dd>{run.step_cursor}</dd><dt>Created</dt><dd>{time(run.created_at)}</dd><dt>Started</dt><dd>{run.started_at ? time(run.started_at) : 'Not started'}</dd><dt>Finished</dt><dd>{run.finished_at ? time(run.finished_at) : 'Not terminal'}</dd><dt>Next due step</dt><dd>{run.next_step_at ? time(run.next_step_at) : 'None'}</dd><dt>Error</dt><dd>{run.error_code ?? 'None'}</dd></dl>
      {active && run.mode === 'simulated' && <><p className="record-disclosure">Cancellation stops this demonstration. {snapshot.current_version ? `Successful demo version ${snapshot.current_version.number} remains available.` : 'No completed preview will be created by cancellation.'}</p><button className="button button-secondary" disabled={runCommands.pending || Boolean(runCommands.recovery)} onClick={() => void runCommands.cancel(run.id)}>Cancel simulation</button></>}
      {run.status==='failed' && run.mode === 'simulated' && <><p className="record-disclosure">Retry creates a linked simulation attempt with the same frozen input. Stale context requires a reviewed new request.</p><button className="button button-primary" disabled={runCommands.pending || Boolean(runCommands.recovery) || Boolean(snapshot.active_run || snapshot.project.archived_at)} onClick={() => void runCommands.retry(run.id)}>Retry simulation</button></>}
      <p className="record-disclosure">Attempt inspection does not change current Brain, version or preview.</p></>}
  </section>;
}
export function DeploymentDetails() {
  const {id}=useWorkspace(); const [cursor,setCursor]=useState(''); const records=useResource<Deployments>(`/projects/${id}/deployments${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`);
  return <><span className="meta">DEPLOYMENT / SIMULATION</span><h2>Internal fixture records</h2><ResourceState {...records} />{records.data?.items.map(record => <article className="request-record" key={record.id}><strong>Simulation · {record.status}</strong><dl><dt>Target</dt><dd>Internal fixture</dd><dt>Version</dt><dd>{record.version_id}</dd><dt>Record</dt><dd>{record.id}</dd><dt>Published</dt><dd>{time(record.created_at)}</dd></dl></article>)}{records.data?.items.length===0 && <p>No simulated deployment records.</p>}<div className="record-pagination">{cursor && <button onClick={() => setCursor('')}>Latest records</button>}{records.data?.next_cursor && <button onClick={() => setCursor(records.data!.next_cursor!)}>Older records</button>}</div><p>These are internal simulation records. Verified production releases appear in Preview and Versions.</p><Link className="text-action" href={`/projects/${id}/versions`}>Inspect production release history ↗</Link></>;
}
