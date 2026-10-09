import type { Metadata } from 'next';
import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-sans/latin-600.css';
import '@fontsource/ibm-plex-mono/latin-400.css';
import '@/styles/globals.css';
import '@/styles/experience.css';
import '@/styles/operating-entry.css';
import '@/styles/project-management.css';
import '@/styles/workspace.css';
import '@/styles/refinement.css';
import '@/styles/premium.css';
import '@/styles/editorial.css';
export const metadata: Metadata = { title: { default: 'F01 — Your idea, a real application', template: '%s · F01' }, description: 'Describe your app, approve the plan, build and preview it. Publish when you are ready, then keep improving it.', icons: { icon: '/favicon.svg' } };
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en" data-theme="light" suppressHydrationWarning><head><script src="/theme-init.js" /></head><body>{children}</body></html>; }
