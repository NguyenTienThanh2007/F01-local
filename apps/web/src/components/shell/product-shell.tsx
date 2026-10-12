'use client';
import Link from 'next/link';
import {ThemeControl} from '@/components/theme/theme-control';
import { usePathname } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';
import type {Session} from '@/lib/projects/contracts';
import { Sheet } from '@/components/ui/sheet';
function RailContent({ close,session }: { close?: () => void;session:Session|null }) {
  const pathname = usePathname();
  const accountName=session ? session.principal.identity_mode==='development' ? 'Founder workspace' : session.principal.display_name : 'Account';
  const identityLabel=session ? session.principal.identity_mode==='development' ? 'Development identity' : 'Authenticated owner' : 'Sign-in required';
  return <>
    <Link className="wordmark" href="/" onClick={close} aria-label="F01 home">F<span>01</span><small>WORKSPACE</small></Link>
    <div className="rail-section-label">PERSONAL WORKSPACE</div>
    <nav className="rail-nav" aria-label="Main navigation"><Link href="/" onClick={close} aria-label="Start"><span className="nav-glyph" aria-hidden="true">⌂</span><span className="nav-text">Start</span></Link><Link href="/projects" onClick={close} aria-label="Projects" aria-current={pathname.startsWith('/projects') ? 'page' : undefined}><span className="nav-glyph" aria-hidden="true">▤</span><span className="nav-text">Projects</span></Link></nav>
    <div className="rail-theme"><ThemeControl/></div><div className="rail-context"><span className="rail-rule"/><p>Ideas become<br/><em>useful things.</em></p><span className="rail-caption">DESCRIBE. BUILD. EVOLVE.</span></div>
    <Link href="/account" className="account-link" onClick={close} aria-label={`${accountName} · ${identityLabel}`}><span className="avatar" aria-hidden="true">{accountName[0]}</span><span className="nav-text">{accountName}<small>{identityLabel}</small></span></Link>
  </>;
}
export function ProductShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [session,setSession]=useState<Session|null>(null),pathname=usePathname();
  useEffect(()=>{const controller=new AbortController();const load=()=>fetch('/api/v1/session',{signal:controller.signal,cache:'no-store'}).then(async response=>{if(!controller.signal.aborted)setSession(response.ok?await response.json() as Session:null);}).catch(()=>{});void load();window.addEventListener('f01-account-updated',load);return()=>{controller.abort();window.removeEventListener('f01-account-updated',load);};},[pathname]);
  return <div className="product-shell"><a href="#main-content" className="skip-link">Skip to content</a><aside className="global-rail"><RailContent session={session} /></aside>
    <header className="mobile-header"><button className="icon-button" aria-label="Open navigation" onClick={() => setOpen(true)}>☰</button><Link href="/">F01</Link><ThemeControl/></header>
    <Sheet open={open} onClose={() => setOpen(false)} title="Navigation"><div className="mobile-rail"><RailContent session={session} close={() => setOpen(false)} /></div></Sheet>
    <main id="main-content" className="product-main" tabIndex={-1}>{children}</main>
  </div>;
}
