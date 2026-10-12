import { errorMessage } from './contracts.ts';
export class ProjectAPIError extends Error {
  code: string;
  status: number;
  constructor(code: string, status: number) { super(errorMessage(code)); this.code = code; this.status = status; }
}
export async function projectRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  // Fetch otherwise sends JSON strings as text/plain. The BFF deliberately
  // requires application/json; preserve that validation at the server boundary.
  if (typeof options.body === 'string' && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const signal = AbortSignal.any([...(options.signal ? [options.signal] : []), AbortSignal.timeout(25000)]);
  let response: Response;
  try { response = await fetch(`/api/v1${path}`, { ...options, headers, signal, cache: 'no-store' }); }
  catch { throw new ProjectAPIError('SERVICE_UNAVAILABLE', 0); }
  let data;
  try { data = await response.json(); } catch { throw new ProjectAPIError('SERVICE_UNAVAILABLE', 0); }
  if (!response.ok) throw new ProjectAPIError(typeof data?.error?.code === 'string' ? data.error.code : 'INTERNAL_ERROR', response.status);
  return data as T;
}
