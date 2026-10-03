import { handleEventStream } from '@/lib/workspace/run-server';
export const dynamic = 'force-dynamic';
export async function GET(request: Request, context: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await context.params;
  return handleEventStream(request, projectId, process.env);
}
