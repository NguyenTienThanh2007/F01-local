import { Workspace } from '@/features/workspace/workspace';
export default async function Layout({ children, params }: { children: React.ReactNode; params: Promise<{ projectId: string }> }) { return <Workspace key={(await params).projectId} id={(await params).projectId}>{children}</Workspace>; }
