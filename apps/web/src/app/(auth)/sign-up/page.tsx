import {AuthScreen} from '@/features/auth/auth-screen';
import {authOptions} from '@/lib/auth/options';
export const dynamic='force-dynamic';
export default async function SignUp({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}){const query=await searchParams;return <AuthScreen signup options={await authOptions(process.env)} error={query.error} returnTo={query.returnTo}/>;}
