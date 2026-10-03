import { handleProjectsRequest } from '@/lib/projects/server';
export const dynamic = 'force-dynamic';
export function GET(request: Request) { return handleProjectsRequest(request, 'projects', undefined, process.env); }
export function POST(request: Request) { return handleProjectsRequest(request, 'projects', undefined, process.env); }
