'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Sheet } from '@/components/ui/sheet';
import { PulseMark } from '@/features/project-pulse/project-pulse';

const destinations = [
  { label: 'Projects', href: '/projects', note: 'Your workspace' },
  { label: 'Templates', href: '#templates', note: 'Starter briefs available' },
  { label: 'Connections', href: '#connections', note: 'Planned ecosystem' },
  { label: 'Docs', href: '#docs', note: 'Planning guide' },
];

export function EntryNavigation() {
  const [open, setOpen] = useState(false);
  return <header className="os-navigation">
    <Link href="/" className="os-wordmark" aria-label="F01 home"><PulseMark /><span>F01<small>SOFTWARE SYSTEM</small></span></Link>
    <nav className="os-nav-links" aria-label="Global navigation">{destinations.map(item => <a key={item.label} href={item.href}>{item.label}{item.label === 'Connections' && <sup>Planned</sup>}</a>)}</nav>
    <div className="os-nav-actions"><Link href="/account" className="os-account">Account</Link><button type="button" className="button button-primary" onClick={() => document.getElementById('brief')?.focus()}>Start a brief<span aria-hidden="true">↗</span></button><button type="button" className="icon-button os-menu-toggle" onClick={() => setOpen(true)} aria-label="Open global navigation">☰</button></div>
    <Sheet open={open} onClose={() => setOpen(false)} title="Explore F01"><nav className="os-mobile-navigation" aria-label="Global navigation">{destinations.map(item => <a key={item.label} href={item.href} onClick={() => setOpen(false)}><span>{item.label}<small>{item.note}</small></span><span aria-hidden="true">↗</span></a>)}<Link href="/account" onClick={() => setOpen(false)}><span>Account<small>Development identity</small></span><span aria-hidden="true">↗</span></Link><Link href="/projects" onClick={() => setOpen(false)}><span>Open workspace<small>Projects and planning</small></span><span aria-hidden="true">↗</span></Link></nav></Sheet>
  </header>;
}
