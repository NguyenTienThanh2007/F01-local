'use client';

import Link from 'next/link';
import { useState } from 'react';
import { ProjectPlanningForm } from '@/features/project-planning/project-planning-form';
import type { StarterId } from '@/features/project-planning/project-starters';
import { LifecycleDemo } from './lifecycle-demo';
import { EntryNavigation } from './entry-navigation';
import { PlatformIndex } from './platform-index';

export function ProductEntry() {
  const [starter, setStarter] = useState<StarterId>('crm');
  return <div className="entry-page os-entry">
    <a href="#main-content" className="skip-link">Skip to content</a>
    <EntryNavigation />
    <main id="main-content" tabIndex={-1}>
      <div className="entry-heading"><div className="entry-eyebrow"><span className="meta">F01 / A SOFTWARE OPERATING WORKSPACE</span><span className="meta">FROM INTENTION TO ITERATION</span></div><div className="os-hero-grid"><div><h1>Describe the outcome.<br /><span>Get working <em>software.</em></span></h1><p>Create a real draft plan or save a project with its Brain, requests and version history. Workspace runs are Simulation; real software execution is the next direction.</p></div><aside className="hero-register" aria-label="Current product availability"><span className="meta">SYSTEM / 01</span><p>One intention.<br />An entire lifecycle.</p><dl><div><dt>Available</dt><dd>Planning · Saved projects</dd></div><div><dt>Ahead</dt><dd>Real generation · Hosting</dd></div></dl></aside></div></div>
      <div className="workbench-rule"><span className="meta">01 / COMMAND</span><span className="workbench-bridge" aria-hidden="true">↳</span><span className="meta">02 / WORKSPACE DEMONSTRATION</span></div>
      <ProjectPlanningForm presentation="home" onStarterChange={setStarter} companion={<LifecycleDemo starter={starter} />} />
      <nav className="os-lifecycle-rail" aria-label="Software lifecycle"><a href="#command-surface"><span className="meta">01 / PLAN + SAVE</span><strong>Create</strong><span aria-hidden="true">→</span></a><a href="#platform"><span className="meta">02 / SIMULATION</span><strong>Run</strong><span aria-hidden="true">→</span></a><a href="#platform"><span className="meta">03 / SAVED CONTEXT</span><strong>Manage</strong><span aria-hidden="true">→</span></a><a href="#platform"><span className="meta">04 / RECORDED INTENT</span><strong>Evolve</strong><span aria-hidden="true">↗</span></a></nav>
      <PlatformIndex />
    </main>
    <footer className="entry-footer"><span>F01 / SOFTWARE SYSTEM</span><span>Planning and saved projects. Execution remains Simulation.</span><Link href="/projects">Open workspace ↗</Link></footer>
  </div>;
}
