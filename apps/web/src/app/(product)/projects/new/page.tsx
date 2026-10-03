import Link from 'next/link';
import { ProjectCreation } from '@/features/projects/project-creation';
import { projectStarters } from '@/features/project-planning/project-starters';
export default async function NewProjectPage({ searchParams }: { searchParams: Promise<{ starter?: string; planning?: string }> }) {
  const { starter, planning } = await searchParams;
  return <div className="page form-page"><Link href="/projects" className="back-link">← Workspace / New project</Link><div className="page-eyebrow"><span>PROJECT / FIRST DRAFT</span><span>PERSISTENCE AVAILABLE</span></div><h1>Good software starts<br />with a clear intention.</h1><p className="form-introduction">Describe the idea. Name the problem. Give it a place in your workspace.</p><ProjectCreation initialIdea={projectStarters.find(item => item.id === starter)?.brief ?? ''} planning={planning === '1'} /></div>;
}
