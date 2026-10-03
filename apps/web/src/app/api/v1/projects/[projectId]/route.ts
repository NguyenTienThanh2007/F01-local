import { handleProjectsRequest } from '@/lib/projects/server';
export const dynamic = 'force-dynamic';
type Context = { params: Promise<{ projectId: string }> };
export async function GET(request: Request, context: Context) { return handleProjectsRequest(request, 'projects', (await context.params).projectId, process.env); }
export async function PATCH(request: Request, context: Context) { return handleProjectsRequest(request, 'projects', (await context.params).projectId, process.env); }
