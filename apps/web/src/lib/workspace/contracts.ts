import type { components } from '@f01/api-client/schema';
export type Snapshot = components['schemas']['WorkspaceSnapshot'];
export type Brain = components['schemas']['BrainView'];
export type Revision = components['schemas']['BrainRevisionRecord'];
export type Revisions = components['schemas']['BrainRevisionList'];
export type RequestRecord = components['schemas']['RequestRecord'];
export type Requests = components['schemas']['RequestList'];
export type ChangeInput = components['schemas']['RecordChange'];
export type Events = components['schemas']['EventList'];
export type Run = components['schemas']['RunRecord'];
export type Runs = components['schemas']['RunList'];
export type StartRun = components['schemas']['StartRun'];
export type Deployments = components['schemas']['DeploymentList'];
export type Versions = components['schemas']['VersionList'];
export type Version = components['schemas']['VersionRecord'];
export type Provenance = components['schemas']['Provenance'];
export type Statement = components['schemas']['Statement'];
export type Descriptor = components['schemas']['PreviewDescriptor'] | components['schemas']['RealPreviewDescriptor'];
export const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function changeInput(text: string, brain: string, version: string | null): ChangeInput | null {
  const value = text.trim();
  return Array.from(value).length >= 20 && Array.from(value).length <= 10000 && uuid.test(brain) && (version === null || uuid.test(version)) ? { text: value, base_brain_revision_id: brain, base_version_id: version } : null;
}
export type ChangeAttempt = { key: string; input: ChangeInput; started: number; simulate?: boolean };
export function readChangeAttempt(storage: Pick<Storage, 'getItem'>, name: string): ChangeAttempt | null {
  try { const v = JSON.parse(storage.getItem(name) ?? 'null');
    return v && uuid.test(v.key) && typeof v.started === 'number' && typeof v.input?.text === 'string' && changeInput(v.input.text, v.input.base_brain_revision_id, v.input.base_version_id) ? v as ChangeAttempt : null;
  } catch { return null; }
}
export function fixturePath(descriptor: Descriptor): string | null {
  return descriptor.kind === 'fixture' && ['crm-v1', 'generic-v1'].includes(descriptor.fixture_id) && (descriptor.fixture_revision == null || descriptor.fixture_revision === 1) ? `/demo-preview/${descriptor.fixture_id}` : null;
}
