import Link from 'next/link';
import { ProjectCreation } from '@/features/projects/project-creation';
import { projectStarters } from '@/features/project-planning/project-starters';
export default async function NewProjectPage({ searchParams }: { searchParams: Promise<{ starter?: string; planning?: string }> }) {
  const { starter, planning } = await searchParams;
  return <div className="page form-page focused-creation"><Link href="/projects" className="back-link">← Projects</Link><div className="page-eyebrow"><span>01 / CREATE</span></div><h1>What do you want to make?</h1><p className="form-introduction">Describe who it is for and what it should do. You will review a plan before anything is built.</p><ProjectCreation initialIdea={projectStarters.find(item => item.id === starter)?.brief ?? ''} planning={planning === '1'} /></div>;
}
