'use client';

import { useEffect, useState } from 'react';
import { ProjectPulse, type Lifecycle } from '@/features/project-pulse/project-pulse';
import type { StarterId } from '@/features/project-planning/project-starters';
import { SampleInterface } from './sample-interface';

const stages: { label: string; pulse: Lifecycle; time: string; event: string; receipt: string; detail: string }[] = [
  { label: 'Understanding', pulse: 'understanding', time: '12:41', event: 'Request understood', receipt: 'INPUT / INTENT', detail: 'The sample brief identifies the people, the problem and the intended outcome.' },
  { label: 'Planning', pulse: 'planning', time: '12:42', event: 'Product plan prepared', receipt: 'SCOPE / DECISIONS', detail: 'The sample scope links the intended outcome to a focused set of features.' },
  { label: 'Building', pulse: 'building', time: '12:44', event: 'Application structure prepared', receipt: 'STRUCTURE / INTERFACE', detail: 'This illustration represents where an implementation would take shape. No code is generated.' },
  { label: 'Verifying', pulse: 'verifying', time: '12:46', event: 'Verification running', receipt: 'CHECK / EVIDENCE', detail: 'A future verification stage would attach build and test evidence here. No checks run in this demo.' },
  { label: 'Live', pulse: 'live', time: '12:48', event: 'Preview ready', receipt: 'PREVIEW / REVIEW', detail: 'The sample interface is ready to inspect. It is an illustration, not a deployed application.' },
];
const scopes: Record<StarterId, { name: string; outcome: string; features: string[] }> = {
  crm: { name: 'Harbor CRM', outcome: 'Keep every customer relationship moving.', features: ['A shared lead register', 'A clear sales pipeline', 'Notes and next steps'] },
  booking: { name: 'Studio daybook', outcome: 'A calmer day. Fewer missed appointments.', features: ['Availability and reservations', 'Appointment reminders', 'A daily operations view'] },
  game: { name: 'Checkpoint', outcome: 'A small challenge worth playing again.', features: ['A geometric maze', 'Collectable checkpoints', 'A personal best time'] },
};

export function LifecycleDemo({ starter = 'crm' }: { starter?: StarterId }) {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [view, setView] = useState<'preview' | 'blueprint'>('preview');
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!preference.matches) setPlaying(true);
    const changed = () => { if (preference.matches) setPlaying(false); };
    preference.addEventListener('change', changed);
    return () => preference.removeEventListener('change', changed);
  }, []);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      if (step >= stages.length - 1) setPlaying(false);
      else setStep(value => value + 1);
    }, 1900);
    return () => window.clearTimeout(timer);
  }, [playing, step]);
  const current = stages[step]!;
  const scope = scopes[starter];
  return <section className="lifecycle-demo os-demo" aria-label="Software lifecycle demonstration">
    <header className="demo-topline"><span className="meta">WORKSPACE / SAMPLE_01</span><span className="demo-disclosure">Visual demonstration</span></header>
    <div className="demo-workspace-heading"><div className="pulse-instrument"><span className="meta">PROJECT PULSE / P{String(step + 1).padStart(2, '0')}</span><ProjectPulse state={current.pulse} label={current.label} animate={playing} variant="instrument" /></div><div className="sample-identity"><strong>{scope.name}</strong><span className="meta">{String(step + 1).padStart(2, '0')} / 05 · SAMPLE STATE</span></div></div>
    <div className="workspace-view-controls"><div className="sample-view-switch" aria-label="Sample workspace view"><button type="button" aria-pressed={view === 'preview'} onClick={() => setView('preview')}>Preview</button><button type="button" aria-pressed={view === 'blueprint'} onClick={() => setView('blueprint')}>Blueprint</button></div><button type="button" className="sample-size-control" aria-pressed={compact} onClick={() => setCompact(value => !value)}>{compact ? 'Full view' : 'Compact view'}<span aria-hidden="true">{compact ? '↔' : '↦'}</span></button></div>
    <div className={`sample-frame ${compact ? 'sample-compact' : ''}`}><div className="sample-frame-bar"><span className="sample-window-marks" aria-hidden="true"><i /><i /><i /></span><span className="meta">{view === 'preview' ? 'APP PREVIEW / ILLUSTRATION' : 'SAMPLE BLUEPRINT / NOT GENERATED'}</span></div>{view === 'preview' ? <SampleInterface starter={starter} /> : <div className="sample-blueprint"><span className="meta">INTENDED OUTCOME</span><h3>{scope.outcome}</h3><ol>{scope.features.map((feature, index) => <li key={feature}><span className="meta">R.0{index + 1}</span>{feature}</li>)}</ol><p>Illustrative scope. Your real plan is created from the brief you submit.</p></div>}</div>
    <div className="demo-trace">
      <div className="trace-heading"><h2>Build Trace<span className="meta">T / 001—005</span></h2><button type="button" className="trace-control" onClick={() => {
        if (playing) setPlaying(false);
        else { if (step === 4) setStep(0); setPlaying(true); }
      }}>{playing ? 'Pause demo' : step === 4 ? 'Replay demo' : 'Play demo'}<span aria-hidden="true">{playing ? 'Ⅱ' : '↗'}</span></button></div>
      <ol>{stages.map((stage, index) => <li key={stage.label} className={index === step ? 'trace-current' : index < step ? 'trace-complete' : 'trace-next'}>
        <button type="button" className="evidence-row" aria-pressed={index === step} onClick={() => { setStep(index); setPlaying(false); }}><span className="evidence-index">{String(index + 1).padStart(2, '0')}</span><time>{stage.time}</time><span className="evidence-event">{stage.event}</span><span className="trace-status" aria-hidden="true">{index < step ? '✓' : index === step ? '↳' : '·'}</span></button>
      </li>)}</ol>
      <div className="trace-receipt"><span className="meta">{current.receipt}</span><p>{current.detail}</p></div>
      <p>Illustrative sequence. No application, build or deployment is executed.</p>
    </div>
  </section>;
}
