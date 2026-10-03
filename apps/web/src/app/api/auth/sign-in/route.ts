import { authRoute } from '@/lib/auth/routes';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export function POST(request:Request){return authRoute(request,'sign-in',process.env);}
