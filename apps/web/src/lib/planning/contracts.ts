export interface ProjectPlan {
  project_title: string;
  product_summary: string;
  target_users: string[];
  core_features: { name: string; description: string }[];
  recommended_stack: { frontend: string; backend: string; database: string; rationale: string };
  implementation_milestones: { title: string; deliverables: string[] }[];
}

export const IDEA_LIMIT = 10_000;
export const planningErrors = {
  VALIDATION_ERROR: { status: 422, message: 'Enter a software idea of 1–10,000 characters.' },
  REQUEST_FORBIDDEN: { status: 403, message: 'This request could not be verified. Reload this page and try again.' },
  UNSUPPORTED_MEDIA_TYPE: { status: 415, message: 'Send the idea as JSON.' },
  REQUEST_TOO_LARGE: { status: 413, message: 'The request is too large. Shorten your idea and try again.' },
  PLANNING_NOT_CONFIGURED: { status: 503, message: 'Planning is not configured on this server. Check the local server configuration and restart the frontend.' },
  AUTHENTICATION_REQUIRED: { status: 503, message: 'The frontend could not authenticate with the backend. Check the shared development configuration and restart both servers.' },
  PROVIDER_NOT_CONFIGURED: { status: 503, message: 'Planning needs a provider key in the backend configuration. Configure the backend and restart it.' },
  PROVIDER_AUTHENTICATION_FAILED: { status: 502, message: 'The planning provider rejected the backend credentials or permissions. Check the backend configuration.' },
  PROVIDER_QUOTA_EXCEEDED: { status: 503, message: 'The planning provider has exhausted its credits or usage allowance. Check the provider account before retrying.' },
  PROVIDER_RATE_LIMITED: { status: 429, message: 'The planning provider is busy. Wait a moment before trying again.' },
  PROVIDER_TIMEOUT: { status: 504, message: 'Planning took too long. Your brief is still here; try again when ready.' },
  PROVIDER_UNAVAILABLE: { status: 503, message: 'The planning service is unavailable. Check that the backend is running, then try again.' },
  PROVIDER_INVALID_RESPONSE: { status: 502, message: 'The planning service returned an invalid plan. Your brief is still here; try again.' },
  PROVIDER_INCOMPLETE_RESPONSE: { status: 502, message: 'The planning provider could not finish the plan. Try a more focused brief.' },
  PROVIDER_REFUSED: { status: 422, message: 'The planning provider declined this idea. Revise the brief and try again.' },
  PROVIDER_ERROR: { status: 502, message: 'The planning provider could not complete this request. Your brief is still here; try again.' },
  INTERNAL_ERROR: { status: 500, message: 'Planning could not be completed. Your brief is still here; try again.' },
} as const;
export type PlanningErrorCode = keyof typeof planningErrors;
export interface PlanningError { code: PlanningErrorCode; message: string; request_id: string }

export function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
export function isErrorCode(value: unknown): value is PlanningErrorCode {
  return typeof value === 'string' && Object.hasOwn(planningErrors, value);
}
function text(value: unknown, max: number): value is string {
  return typeof value === 'string' && value.trim().length > 0 && Array.from(value).length <= max;
}
function keys(value: unknown, fields: string[]): value is Record<string, unknown> {
  return record(value) && Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function list(value: unknown, max: number, item: (value: unknown) => boolean): boolean {
  return Array.isArray(value) && value.length >= 1 && value.length <= max && value.every(item);
}
export function parseIdea(value: unknown): string | null {
  if (!keys(value, ['idea']) || typeof value.idea !== 'string') return null;
  const idea = value.idea.trim();
  return text(idea, IDEA_LIMIT) ? idea : null;
}
// Mirrors the bounded Pydantic ProjectPlan contract; no provider wire types enter the UI.
export function isProjectPlan(value: unknown): value is ProjectPlan {
  if (!keys(value, ['project_title', 'product_summary', 'target_users', 'core_features', 'recommended_stack', 'implementation_milestones'])) return false;
  const stack = value.recommended_stack;
  return text(value.project_title, 100) && text(value.product_summary, 1000)
    && list(value.target_users, 10, item => text(item, 200))
    && list(value.core_features, 16, item => keys(item, ['name', 'description']) && text(item.name, 100) && text(item.description, 1000))
    && keys(stack, ['frontend', 'backend', 'database', 'rationale'])
    && text(stack.frontend, 200) && text(stack.backend, 200) && text(stack.database, 200) && text(stack.rationale, 1000)
    && list(value.implementation_milestones, 12, item => keys(item, ['title', 'deliverables']) && text(item.title, 100) && list(item.deliverables, 10, deliverable => text(deliverable, 200)));
}
