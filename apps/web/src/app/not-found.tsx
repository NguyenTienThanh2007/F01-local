import Link from 'next/link';
export default function NotFound() { return <main className="sign-in"><span className="meta">404</span><h1>This page isn’t available.</h1><p>Return to your projects to continue.</p><Link href="/projects" className="button button-primary">Projects</Link></main>; }
