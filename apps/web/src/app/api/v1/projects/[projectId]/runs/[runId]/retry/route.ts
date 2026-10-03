import { handleRunRequest } from '@/lib/workspace/run-server';
export const dynamic = 'force-dynamic';
export async function POST(request: Request, context: { params: Promise<{ projectId: string; runId: string }> }) {
  const { projectId, runId } = await context.params;
  return handleRunRequest(request, projectId, 'retry', process.env, runId);
}
