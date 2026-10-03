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
export const metadata: Metadata = { title: { default: 'F01 — Software, with a next chapter', template: '%s · F01' }, description: 'Start with a product plan. A workspace built toward creating, running, managing and evolving software.', icons: { icon: '/favicon.svg' } };
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html>; }
