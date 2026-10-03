import { validateEnvironment } from './src/lib/config/environment.mjs';
import { loadRootEnvironment } from './src/lib/config/root-environment.mjs';
loadRootEnvironment(process.env);
validateEnvironment(process.env);
export default {
  poweredByHeader: false,
  async headers() {
    return [{ source: '/:path*', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' }
    ] }];
  }
};
