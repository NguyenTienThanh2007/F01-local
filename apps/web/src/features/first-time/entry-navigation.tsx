'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Sheet } from '@/components/ui/sheet';
import { PulseMark } from '@/features/project-pulse/project-pulse';

const destinations = [
  { label: 'Projects', href: '/projects', note: 'Your workspace' },
  { label: 'Examples', href: '#templates', note: 'Start with a useful brief' },
  { label: 'Docs', href: '#docs', note: 'Planning guide' },
];

export function EntryNavigation() {
  const [open, setOpen] = useState(false);
  return <header className="os-navigation">
    <Link href="/" className="os-wordmark" aria-label="F01 home"><PulseMark /><span>F01<small>SOFTWARE SYSTEM</small></span></Link>
    <nav className="os-nav-links" aria-label="Global navigation">{destinations.map(item => <a key={item.label} href={item.href}>{item.label}{item.label === 'Connections' && <sup>Planned</sup>}</a>)}</nav>
    <div className="os-nav-actions"><Link href="/sign-in" className="os-account">Sign in</Link><Link className="button button-secondary" href="/projects">Open workspace</Link><button type="button" className="icon-button os-menu-toggle" onClick={() => setOpen(true)} aria-label="Open global navigation">☰</button></div>
    <Sheet open={open} onClose={() => setOpen(false)} title="Explore F01"><nav className="os-mobile-navigation" aria-label="Global navigation">{destinations.map(item => <a key={item.label} href={item.href} onClick={() => setOpen(false)}><span>{item.label}<small>{item.note}</small></span><span aria-hidden="true">↗</span></a>)}<Link href="/account" onClick={() => setOpen(false)}><span>Account<small>Profile and secure access</small></span><span aria-hidden="true">↗</span></Link><Link href="/projects" onClick={() => setOpen(false)}><span>Open workspace<small>Projects and planning</small></span><span aria-hidden="true">↗</span></Link></nav></Sheet>
  </header>;
}
