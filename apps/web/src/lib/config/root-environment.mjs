import { readFileSync } from 'node:fs';
import { parseEnv } from 'node:util';

const rootEnvironment = new URL('../../../../../.env', import.meta.url);
const webKeys = ['APP_ENV', 'AUTH_MODE', 'EXECUTION_MODE', 'API_INTERNAL_URL', 'DEV_API_TOKEN', 'AUTH_GATEWAY_TOKEN', 'NEXT_PUBLIC_APP_URL'];

export function loadRootEnvironment(env, path = rootEnvironment) {
  let values;
  try {
    values = parseEnv(readFileSync(path, 'utf8'));
  } catch (error) {
    if (error?.code === 'ENOENT') return;
    throw new Error('The project environment file could not be loaded.');
  }
  // Only web settings cross this boundary. Never read apps/api/.env.
  for (const key of webKeys) {
    if (env[key] === undefined && values[key] !== undefined) env[key] = values[key];
  }
}
