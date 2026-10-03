import { errorMessage } from './contracts';
export class ProjectAPIError extends Error {
  constructor(public code: string, public status: number) { super(errorMessage(code)); }
}
export async function projectRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api/v1${path}`, { ...options, cache: 'no-store' }); }
  catch { throw new ProjectAPIError('SERVICE_UNAVAILABLE', 0); }
  let data;
  try { data = await response.json(); } catch { throw new ProjectAPIError('SERVICE_UNAVAILABLE', 0); }
  if (!response.ok) throw new ProjectAPIError(typeof data?.error?.code === 'string' ? data.error.code : 'INTERNAL_ERROR', response.status);
  return data as T;
}
