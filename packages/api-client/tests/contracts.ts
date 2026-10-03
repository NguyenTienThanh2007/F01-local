import type { Client } from "openapi-fetch";
import type { paths, components } from "../src/schema";

type CreateProject = components["schemas"]["CreateProject"];
const valid: CreateProject = { brief: "Build a customer relationship management application." };
void valid;
// @ts-expect-error Execution mode is owned by the backend.
const invalid: CreateProject = { brief: "Build an app", mode: "real" };
void invalid;

export function checkClientContract(client: Client<paths>) {
  void client.POST("/v1/projects", {
    body: valid,
    params: { header: { "idempotency-key": "contract-test" } },
  });
  // @ts-expect-error The API requires an idempotency header.
  void client.POST("/v1/projects", { body: valid });
  // @ts-expect-error Run execution is a later milestone and has no endpoint.
  void client.POST("/v1/projects/{project_id}/runs", { body: {} });
}

export function checkM4Contract(client: Client<paths>, projectId: string, brainId: string) {
  void client.POST("/v1/projects/{project_id}/requests", {
    params: { path: { project_id: projectId }, header: { "idempotency-key": "m4-contract" } },
    body: { text: "Record a change", base_brain_revision_id: brainId, base_version_id: null },
  });
  // @ts-expect-error A change must identify the Brain context.
  void client.POST("/v1/projects/{project_id}/requests", { params: { path: { project_id: projectId }, header: { "idempotency-key": "key" } }, body: { text: "Missing base", base_version_id: null } });
}
