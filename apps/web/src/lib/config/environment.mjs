export function validateEnvironment(env) {
  const appEnvironment = env.APP_ENV ?? 'development';
  const authMode = env.AUTH_MODE ?? 'development';
  if (!['development', 'test', 'preview', 'production'].includes(appEnvironment)) {
    throw new Error('APP_ENV is invalid.');
  }
  if (!['development','oidc'].includes(authMode)) throw new Error('AUTH_MODE is invalid.');
  if (appEnvironment === 'production' && authMode === 'development') throw new Error('Development identity cannot run in production.');
  if (authMode === 'oidc' && (env.AUTH_GATEWAY_TOKEN ?? '').length < 32) throw new Error('Configure the private authentication gateway credential.');
  if (env.EXECUTION_MODE && env.EXECUTION_MODE !== 'simulated') {
    throw new Error('This phase supports simulated execution only.');
  }
  return { appEnvironment, authMode };
}
