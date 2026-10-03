'use client';
import { Button } from '@/components/ui/button';
import { ProjectPulse } from '@/features/project-pulse/project-pulse';
export default function ErrorPage({ reset }: { reset: () => void }) {
  return <div className="page narrow-page workspace-error" role="alert"><span className="page-eyebrow">WORKSPACE / NEEDS ATTENTION</span><ProjectPulse state="error" label="Unable to open workspace" /><h1>Let’s try that again.</h1><p className="muted">This view couldn’t be loaded. Try opening it again.</p><Button onClick={reset}>Try again</Button></div>;
}
