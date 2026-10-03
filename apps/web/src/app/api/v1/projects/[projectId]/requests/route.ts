import { handleWorkspaceRequest } from '@/lib/workspace/server';
export async function GET(request: Request, { params }: { params: Promise<{ projectId: string }> }) { return handleWorkspaceRequest(request, (await params).projectId, 'requests', process.env); }
export async function POST(request: Request, { params }: { params: Promise<{ projectId: string }> }) { return handleWorkspaceRequest(request, (await params).projectId, 'requests', process.env); }
