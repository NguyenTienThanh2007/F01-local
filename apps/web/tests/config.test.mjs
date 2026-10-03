import test from 'node:test';
import assert from 'node:assert/strict';
import { validateEnvironment } from '../src/lib/config/environment.mjs';
import { loadRootEnvironment } from '../src/lib/config/root-environment.mjs';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
test('development identity cannot run in production', () => {
  assert.throws(() => validateEnvironment({ APP_ENV: 'production' }), /cannot run in production/);
});
test('real execution cannot be enabled by configuration', () => {
  assert.throws(() => validateEnvironment({ EXECUTION_MODE: 'real' }), /simulated execution only/);
});
test('root configuration loads only selected web settings and preserves process overrides', () => {
  const dir = mkdtempSync(join(tmpdir(), 'f01-config-'));
  try {
    const path = join(dir, 'fixture.env');
    writeFileSync(path, 'DEV_API_TOKEN=synthetic-configuration-token\nAPI_INTERNAL_URL=http://127.0.0.1:8000\nOPENAI_API_KEY=synthetic-backend-only\nDATABASE_URL=private-backend-setting\n');
    const env = { API_INTERNAL_URL: 'http://127.0.0.1:9000' };
    loadRootEnvironment(env, path);
    assert.equal(env.DEV_API_TOKEN, 'synthetic-configuration-token');
    assert.equal(env.API_INTERNAL_URL, 'http://127.0.0.1:9000');
    assert.equal(env.OPENAI_API_KEY, undefined);
    assert.equal(env.DATABASE_URL, undefined);
    loadRootEnvironment(env, join(dir, 'missing.env'));
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
