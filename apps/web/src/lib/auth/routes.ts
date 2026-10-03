import 'server-only';
import { configuration, sameOrigin } from '../projects/server.ts';
import { cookieNames, readCookie } from './session.ts';
type Environment=Record<string,string|undefined>;
function cookie(name:string,value:string,origin:URL,maxAge:number) { return `${name}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${origin.protocol==='https:' ? '; Secure' : ''}`; }
function redirect(origin:URL,path:string) { return new Response(null,{status:303,headers:{Location:new URL(path,origin).href,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'}}); }
export async function authRoute(request:Request,action:'sign-in'|'callback'|'sign-out',env:Environment,send:typeof fetch=fetch) {
  let config:ReturnType<typeof configuration>;
  try{config=configuration(env);}catch{return Response.json({error:'Identity service is not configured.'},{status:503});}
  if(config.authMode!=='oidc')return redirect(config.origin,'/sign-in');
  const names=cookieNames(config.origin);
  if(action!=='callback' && (request.method!=='POST'||!sameOrigin(request,config.origin,config.local)))return Response.json({error:'A same-origin POST is required.'},{status:403});
  if(action==='callback' && request.method!=='GET')return new Response(null,{status:405});
  const call=async(path:string,body:object)=>send(new URL(`/v1/auth/${path}`,config.base),{method:'POST',redirect:'error',cache:'no-store',headers:{Authorization:`Bearer ${config.token}`,'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
  try{
    if(action==='sign-in'){
      const result=await call('start',{}); if(!result.ok)return redirect(config.origin,'/sign-in?error=unavailable');
      const data=await result.json() as {authorization_url:string;binding:string};
      if(!/^[A-Za-z0-9_-]{40,100}$/.test(data.binding))throw new Error();
      const response=redirect(config.origin,'/projects');response.headers.set('Location',data.authorization_url);response.headers.append('Set-Cookie',cookie(names.login,data.binding,config.origin,300));return response;
    }
    if(action==='callback'){
      const query=new URL(request.url).searchParams, binding=readCookie(request,names.login);
      const state=query.get('state'),code=query.get('code');
      if(!binding||!state||!code||query.has('error')||state.length>100||code.length>2048)throw new Error();
      const result=await call('callback',{state,code,binding});if(!result.ok)throw new Error();
      const data=await result.json() as {session:string;csrf:string;expires_at:string};
      if(![data.session,data.csrf].every(value=>/^[A-Za-z0-9_-]{40,100}$/.test(value)))throw new Error();
      const remaining=(Date.parse(data.expires_at)-Date.now())/1000;if(!Number.isFinite(remaining)||remaining<=0)throw new Error();
      const response=redirect(config.origin,'/projects');const age=Math.min(86400,Math.floor(remaining));
      response.headers.append('Set-Cookie',cookie(names.session,data.session,config.origin,age));response.headers.append('Set-Cookie',cookie(names.csrf,data.csrf,config.origin,age));response.headers.append('Set-Cookie',cookie(names.login,'',config.origin,0));return response;
    }
    const session=readCookie(request,names.session),csrf=readCookie(request,names.csrf);
    if(session&&csrf){const result=await call('logout',{session,csrf});if(!result.ok&&result.status!==401)return redirect(config.origin,'/account?error=sign-out');}
    const response=redirect(config.origin,'/sign-in?signed_out=1');for(const name of Object.values(names))response.headers.append('Set-Cookie',cookie(name,'',config.origin,0));return response;
  }catch{
    if(action==='sign-out')return redirect(config.origin,'/account?error=sign-out');
    const response=redirect(config.origin,'/sign-in?error=unavailable');response.headers.append('Set-Cookie',cookie(names.login,'',config.origin,0));return response;
  }
}
