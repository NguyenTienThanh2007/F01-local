import { handleRunRequest } from '@/lib/workspace/run-server';
export const dynamic = 'force-dynamic';
export async function GET(request: Request, context: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await context.params;
  return handleRunRequest(request, projectId, 'deployments', process.env);
}
