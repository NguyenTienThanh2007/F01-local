import { authRoute } from '@/lib/auth/routes';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export function GET(request:Request){return authRoute(request,'callback',process.env);}
