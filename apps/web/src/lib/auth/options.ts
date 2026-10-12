import 'server-only';
import {configuration} from '../projects/server';
export async function authOptions(env:Record<string,string|undefined>){
 if(env.AUTH_MODE!=='oidc')return {oidc:false,google:false,email:false,available:true};
 try{const config=configuration(env),response=await fetch(new URL('/v1/auth/options',config.base),{headers:{Authorization:`Bearer ${config.token}`},cache:'no-store',redirect:'error',signal:AbortSignal.timeout(5000)});
 if(!response.ok)throw Error();const data:unknown=await response.json();if(!data||typeof data!=='object'||!('google'in data)||!('email'in data)||typeof data.google!=='boolean'||typeof data.email!=='boolean')throw Error();
 return {oidc:true,google:data.google,email:data.email,available:true};}catch{return {oidc:true,google:false,email:false,available:false};}
}
