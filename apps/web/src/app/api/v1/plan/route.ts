import { handlePlanRequest } from '@/lib/planning/server';

export const runtime = 'nodejs';

export async function POST(request: Request): Promise<Response> {
  return handlePlanRequest(request, process.env);
}
