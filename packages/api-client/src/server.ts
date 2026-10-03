import "server-only";
import createClient from "openapi-fetch";
import type { paths } from "./schema";

/** Private backend transport. Import generated schema types separately in browser code. */
export function createBackendClient(options: {
  baseUrl: string;
  bearerToken?: string;
  /** Compatibility for explicit local development callers. */
  developmentToken?: string;
  fetch?: typeof globalThis.fetch;
  headers?: Record<string,string>;
}) {
  const origin = new URL(options.baseUrl);
  if (!/^https?:$/.test(origin.protocol) || origin.username || origin.password || origin.search || origin.hash || origin.pathname !== "/") {
    throw new Error("Configure a backend HTTP origin.");
  }
  const transport = options.fetch ?? globalThis.fetch;
  const credential = options.bearerToken ?? options.developmentToken;
  if (!credential) throw new Error('Configure a private bearer credential.');
  return createClient<paths>({
    baseUrl: origin.origin,
    headers: { ...options.headers, Authorization: `Bearer ${credential}` },
    fetch: (request) => transport(request, { redirect: "error", cache: "no-store" }),
  });
}
