'use client';
import Link from 'next/link';
import {useEffect,useState} from 'react';
import {projectRequest} from '@/lib/projects/browser';
import type {Session} from '@/lib/projects/contracts';
export default function AccountPage(){
 const [signOutError,setSignOutError]=useState(false);
 useEffect(()=>setSignOutError(new URL(location.href).searchParams.get('error')==='sign-out'),[]);
 const [session,setSession]=useState<Session|null>(null),[pending,setPending]=useState(true),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
 useEffect(()=>{const controller=new AbortController();setPending(true);projectRequest<Session>('/session',{signal:controller.signal}).then(value=>{setSession(value);setError('');}).catch(e=>{if(!controller.signal.aborted){setSession(null);setError(e.message);}}).finally(()=>{if(!controller.signal.aborted)setPending(false);});return()=>controller.abort();},[attempt]);
 return <div className="page narrow-page"><span className="page-eyebrow">WORKSPACE / ACCOUNT</span><h1>Account</h1>{signOutError&&<p role="alert">Sign-out could not be confirmed. Your session cookie is retained; retry when the identity service is available.</p>}{pending&&<p role="status">Checking your session…</p>}{error&&<><p role="alert">{error}</p><Link className="button button-primary" href="/sign-in">Sign in</Link><button className="button button-secondary" onClick={()=>setAttempt(v=>v+1)}>Retry session</button></>}{session&&<section className="detail-section"><h2>{session.principal.display_name}</h2><p>{session.principal.identity_mode==='oidc'?'Authenticated owner':'Development identity'}</p><p className="muted">Projects are authorized by your stable internal user identity. Team collaboration is not available.</p>{session.expires_at&&<p>Session expires {new Date(session.expires_at).toLocaleString()}. Reauthenticate when it expires.</p>}{session.principal.identity_mode==='oidc'&&<form method="post" action="/api/auth/sign-out"><button className="button button-secondary" type="submit">Sign out</button></form>}</section>}</div>;
}
