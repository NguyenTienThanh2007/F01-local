import {AuthScreen} from '@/features/auth/auth-screen';
import {authOptions} from '@/lib/auth/options';
export const dynamic='force-dynamic';
export default async function SignIn({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}){const query=await searchParams;return <AuthScreen options={await authOptions(process.env)} error={query.error} signedOut={Boolean(query.signed_out)} returnTo={query.returnTo}/>;}
