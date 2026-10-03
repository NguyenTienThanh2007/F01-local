import { ProjectDashboard } from '@/features/projects/project-dashboard';
export default async function ProjectsPage({ searchParams }: { searchParams: Promise<{ q?: string; status?: string; archived?: string; cursor?: string }> }) {
  const params = await searchParams;
  return <ProjectDashboard key={`${params.q}|${params.status}|${params.archived}|${params.cursor}`} q={params.q ?? ''} status={params.status ?? ''} archived={params.archived === 'true'} cursor={params.cursor ?? ''} />;
}
