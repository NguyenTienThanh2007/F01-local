import 'server-only';
export interface Principal { display_name: string; identity_mode: 'development' }
export function getDevelopmentPrincipal(): Principal {
  if (process.env.APP_ENV === 'production' || (process.env.AUTH_MODE ?? 'development') !== 'development') {
    throw new Error('Development identity is unavailable.');
  }
  return { display_name: 'Founder workspace', identity_mode: 'development' };
}
