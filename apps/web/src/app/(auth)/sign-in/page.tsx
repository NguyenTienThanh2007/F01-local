import Link from 'next/link';
export const dynamic='force-dynamic';
export default async function SignIn({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}) {
  const query=await searchParams,oidc=process.env.AUTH_MODE==='oidc';
  return <main className="sign-in"><span className="wordmark">F01</span><span className="meta">PRIVATE WORKSPACE / SIGN IN</span><h1>Your workspace</h1>
    {query.error&&<p role="alert">Sign-in could not be completed. Check your identity service and try again.</p>}
    {query.signed_out&&<p role="status">You are signed out of this workspace.</p>}
    {oidc ? <><p>Return to your projects, their context and the next version of your software.</p><form method="post" action="/api/auth/sign-in"><button className="button button-primary" type="submit">Sign in securely</button></form></> : <><p>Local development mode uses an explicit development owner. Production sign-in requires OIDC configuration.</p><Link className="button button-primary" href="/projects">Open development workspace</Link></>}
  </main>;
}
