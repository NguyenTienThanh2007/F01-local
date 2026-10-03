import { handleWorkspaceRequest } from '@/lib/workspace/server';
export async function GET(request: Request, { params }: { params: Promise<{ projectId: string; versionId: string }> }) { const { projectId, versionId } = await params; return handleWorkspaceRequest(request, projectId, 'versions', process.env, versionId); }
