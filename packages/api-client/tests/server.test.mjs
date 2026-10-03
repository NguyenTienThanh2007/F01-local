import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { createBackendClient } from "../src/server.ts";

test("generated client uses the private fixed-origin transport and preserves metadata headers", async () => {
  let observed;
  const client = createBackendClient({
    baseUrl: "http://127.0.0.1:8000",
    developmentToken: "synthetic-client-test-token",
    fetch: async (request, init) => {
      observed = { request, init };
      return Response.json({ items: [], next_cursor: null }, { headers: { ETag: '"metadata"' } });
    },
  });
  const result = await client.GET("/v1/projects", { params: { query: { limit: 20 } } });
  assert.deepEqual(result.data, { items: [], next_cursor: null });
  assert.equal(result.response.headers.get("ETag"), '"metadata"');
  assert.equal(observed.request.url, "http://127.0.0.1:8000/v1/projects?limit=20");
  assert.equal(observed.request.headers.get("Authorization"), "Bearer synthetic-client-test-token");
  assert.equal(observed.init.redirect, "error");
  assert.equal(observed.init.cache, "no-store");
});

test("private transport rejects browser/default imports and non-origin URLs", () => {
  for (const baseUrl of ["http://user:password@localhost", "http://localhost/arbitrary", "http://localhost/?query=1", "file:///tmp/api"]) {
    assert.throws(() => createBackendClient({ baseUrl, developmentToken: "synthetic" }));
  }
  const result = spawnSync(process.execPath, ["--input-type=module", "-e", "import('./src/server.ts')"], {
    cwd: new URL("..", import.meta.url), encoding: "utf8", env: { ...process.env, NODE_OPTIONS: "" },
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /cannot be imported from a Client Component/);
});
