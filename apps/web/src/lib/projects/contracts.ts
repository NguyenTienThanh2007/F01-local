import type { components } from '@f01/api-client/schema';
export type Project = components['schemas']['ProjectSummary'];
export type ProjectList = components['schemas']['ProjectList'];
export type Created = components['schemas']['ProjectCreated'];
export type CreateInput = components['schemas']['CreateProject'];
export type UpdateInput = components['schemas']['UpdateProject'];
export type Session = components['schemas']['SessionView'];
export const states = ['idle', 'understanding', 'planning', 'building', 'verifying', 'deploying', 'live', 'error'] as const;
export const stateNames: Record<Project['lifecycle'], string> = { idle: 'Idle', understanding: 'Understanding', planning: 'Planning', building: 'Building', verifying: 'Verifying', deploying: 'Deploying', live: 'Live · Demo', error: 'Needs attention' };
export function createInput(title: string, brief: string): CreateInput | null {
  const text = brief.trim(), name = title.trim();
  if (Array.from(name).length > 100 || Array.from(text).length < 20 || Array.from(text).length > 10000) return null;
  return { title: name || null, brief: text };
}
export const errors: Record<string, string> = {
  ACTIVE_RUN_EXISTS: 'This project has a queued or running build. Wait for it to finish or cancel it in Run details.',
  RUN_NOT_RETRYABLE: 'Only a failed build can be retried. Inspect the current run state.',
  STALE_BRAIN_REVISION: 'The project changed since this draft began. Your text is preserved. Review the current project before recording it.',
  EXECUTION_UNAVAILABLE: 'The build runtime is unavailable. Your plan is saved; try again when the runtime is ready.',
  PLAN_REVIEW_REQUIRED: 'Review the current plan before starting a build.',
  CLEANUP_PENDING: 'The previous build is still being cleaned up. Your last successful version is preserved. Try again after cleanup.',
  SOURCE_BASE_UNAVAILABLE: 'The current source is unavailable for this update. Inspect its saved version before retrying.',
  BUILD_TIMEOUT: 'This build reached its time limit. Your last successful version is preserved.',
  BUILD_CANCELED: 'This build was canceled. Your last successful version is preserved.',
  STALE_BASE_VERSION: 'The current version changed since this draft began. Your text is preserved. Review the current project before recording it.',
  PROJECT_ARCHIVED: 'Unarchive this project before recording a change.',
  UNSUPPORTED_BRAIN_SCHEMA: 'This Brain schema is not supported. The saved content has not been changed.',
  METADATA_CONFLICT: 'This project changed elsewhere. Review the latest title and archive state, then retry your change.',
  IDEMPOTENCY_IN_PROGRESS: 'This command is still being resolved. Retry with the same saved key and input.',
  IDEMPOTENCY_KEY_REUSED: 'This key belongs to another input. Inspect saved history before starting another command.',
  VALIDATION_ERROR: 'Check the request fields. Titles use up to 100 characters; briefs and change requests use 20–10,000 characters.',
  PLANNING_STALE_CONTEXT: 'Project context changed. Your request is preserved. Review the current context before making a new plan.',
  PLANNING_RATE_LIMITED: 'Your planning request allowance is temporarily exhausted. Try later.',
  PLANNING_BUDGET_EXCEEDED: 'Your planning token budget is exhausted for this UTC day.',
  PLANNING_IN_PROGRESS: 'A planning attempt is pending. Resolve its saved status before trying again.',
  PLANNING_CONTEXT_TOO_LARGE: 'This planning context exceeds the configured input allowance.',
  PLANNING_ABANDONED: 'The attempt passed its deadline without confirmation. Review context and start a new attempt.',
  PLANNING_CANCELED: 'The planning attempt was canceled. No proposal was published.',
  NOT_FOUND: 'This project is unavailable.', AUTHENTICATION_REQUIRED: 'Sign in again to access your workspace.',
  REQUEST_FORBIDDEN: 'This request must come from your workspace.',
  PROJECTS_NOT_CONFIGURED: 'The project service is not configured. Check the server connection and retry.',
  SERVICE_UNAVAILABLE: 'The project service is unavailable. Your input is preserved; retry when the connection returns.',
  INTERNAL_ERROR: 'The request could not be completed. Your input is preserved; retry safely.',
};
export function errorMessage(code: string): string { return errors[code] ?? errors.INTERNAL_ERROR!; }
export function projectETag(project: Project): string { return `"project-${project.id}-m${project.metadata_version}"`; }
