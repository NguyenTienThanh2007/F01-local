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
      <div className="entry-heading"><div className="entry-eyebrow"><span className="meta">F01 / A SOFTWARE OPERATING WORKSPACE</span><span className="meta">FROM INTENTION TO ITERATION</span></div><div className="os-hero-grid"><div><h1>Describe the outcome.<br /><span>Get working <em>software.</em></span></h1><p>Start with an intention. Review the plan, follow the build and preview your product before publishing. Your Project Brain and version history connect every next step.</p></div><aside className="hero-register" aria-label="F01 product lifecycle"><span className="meta">SYSTEM / 01</span><p>One intention.<br />An entire lifecycle.</p><dl><div><dt>Start</dt><dd>Brief · Reviewed plan</dd></div><div><dt>Continue</dt><dd>Build · Preview · Release</dd></div></dl></aside></div></div>
      <div className="workbench-rule"><span className="meta">01 / COMMAND</span><span className="workbench-bridge" aria-hidden="true">↳</span><span className="meta">02 / WORKSPACE DEMONSTRATION</span></div>
      <ProjectPlanningForm presentation="home" onStarterChange={setStarter} companion={<LifecycleDemo starter={starter} />} />
      <nav className="os-lifecycle-rail" aria-label="Software lifecycle"><a href="#command-surface"><span className="meta">01 / PLAN + SAVE</span><strong>Create</strong><span aria-hidden="true">→</span></a><a href="#platform"><span className="meta">02 / BUILD + VERIFY</span><strong>Run</strong><span aria-hidden="true">→</span></a><a href="#platform"><span className="meta">03 / SAVED CONTEXT</span><strong>Manage</strong><span aria-hidden="true">→</span></a><a href="#platform"><span className="meta">04 / MODIFY + REBUILD</span><strong>Evolve</strong><span aria-hidden="true">↗</span></a></nav>
      <PlatformIndex />
    </main>
    <footer className="entry-footer"><span>F01 / SOFTWARE SYSTEM</span><span>From the first intention to the next verified version.</span><Link href="/projects">Open workspace ↗</Link></footer>
  </div>;
}
