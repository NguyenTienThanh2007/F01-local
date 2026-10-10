import 'server-only';
import {configuration,sameOrigin} from '../projects/server.ts';
import {cookieNames,readCookie} from './session.ts';
import {authDestination} from './navigation.ts';
type Environment=Record<string,string|undefined>;
function cookie(name:string,value:string,origin:URL,maxAge:number){return `${name}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${origin.protocol==='https:'?'; Secure':''}`;}
function redirect(origin:URL,path:string){return new Response(null,{status:303,headers:{Location:new URL(path,origin).href,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});}
async function formInput(request:Request){if(!request.body)return new URLSearchParams();if(request.headers.get('content-type')?.split(';')[0]!=='application/x-www-form-urlencoded')throw Error();const reader=request.body.getReader();let text='',size=0;const decoder=new TextDecoder('utf-8',{fatal:true});try{for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>2048)throw Error();text+=decoder.decode(value,{stream:true});}text+=decoder.decode();}finally{await reader.cancel().catch(()=>{});}const form=new URLSearchParams(text);for(const key of form.keys())if(!['method','intent','returnTo'].includes(key)||form.getAll(key).length!==1)throw Error();return form;}
function savedDestination(request:Request,name:string){const parts=(request.headers.get('cookie')??'').split(';').map(v=>v.trim()).filter(v=>v.startsWith(name+'='));if(parts.length!==1)return '/projects';try{return authDestination(decodeURIComponent(parts[0]!.slice(name.length+1)));}catch{return '/projects';}}
class LoginFailure extends Error {reason:string;constructor(reason:string){super('Login unavailable');this.reason=reason;}}
async function json(response:Response){const reader=response.body?.getReader();if(!reader)throw Error();let bytes=0;const chunks:Uint8Array[]=[];try{for(;;){const {done,value}=await reader.read();if(done)break;bytes+=value.length;if(bytes>20000)throw Error();chunks.push(value);}}finally{await reader.cancel().catch(()=>{});}const buffer=new Uint8Array(bytes);let offset=0;for(const chunk of chunks){buffer.set(chunk,offset);offset+=chunk.length;}return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(buffer));}
export async function authRoute(request:Request,action:'sign-in'|'callback'|'sign-out',env:Environment,send:typeof fetch=fetch){
 let config:ReturnType<typeof configuration>;try{config=configuration(env);}catch{return Response.json({error:'Identity service is not configured.'},{status:503,headers:{'Cache-Control':'no-store'}});}
 if(config.authMode!=='oidc')return redirect(config.origin,'/sign-in');
 const names=cookieNames(config.origin),returnName=names.login+'-return';let destination=savedDestination(request,returnName);
 if(action!=='callback'&&(request.method!=='POST'||!sameOrigin(request,config.origin,config.local)))return Response.json({error:'A same-origin POST is required.'},{status:403});
 if(action==='callback'&&request.method!=='GET')return new Response(null,{status:405});
 const call=async(path:string,body:object)=>{const result=await send(new URL(`/v1/auth/${path}`,config.base),{method:'POST',redirect:'error',cache:'no-store',headers:{Authorization:`Bearer ${config.token}`,'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});if(!result.ok){const data=await json(result);const code=data?.error?.code;throw new LoginFailure(code==='EMAIL_VERIFICATION_REQUIRED'?'verification':code==='AUTH_RATE_LIMITED'?'limited':code==='AUTH_METHOD_UNAVAILABLE'?'method':path==='callback'&&result.status===401?'expired':'unavailable');}return json(result);};
 try{
  if(action==='sign-in'){
   const form=await formInput(request),method=form.get('method')??'hosted',intent=form.get('intent')??'sign-in';destination=authDestination(form.get('returnTo'));
   if(!['hosted','google','email'].includes(method)||!['sign-in','sign-up'].includes(intent))throw Error();
   const data=await call('start',{method,intent});if(typeof data.binding!=='string'||!/^[A-Za-z0-9_-]{40,100}$/.test(data.binding))throw Error();const url=new URL(data.authorization_url);
   if(url.username||url.password||url.hash||!(url.protocol==='https:'||env.APP_ENV!=='production'&&url.protocol==='http:'&&config.local.includes(url.hostname)))throw Error();
   const response=redirect(config.origin,'/projects');response.headers.set('Location',url.href);response.headers.append('Set-Cookie',cookie(names.login,data.binding,config.origin,300));response.headers.append('Set-Cookie',cookie(returnName,encodeURIComponent(destination),config.origin,300));return response;
  }
  if(action==='callback'){
   const query=new URL(request.url).searchParams,binding=readCookie(request,names.login),state=query.get('state'),code=query.get('code');
   if(query.has('error'))throw new LoginFailure(query.get('error')==='access_denied'?'canceled':'unavailable');
   if(!binding||!state||!code||query.getAll('state').length!==1||query.getAll('code').length!==1||state.length>100||code.length>2048)throw new LoginFailure('expired');
   const data=await call('callback',{state,code,binding});if(![data.session,data.csrf].every(value=>typeof value==='string'&&/^[A-Za-z0-9_-]{40,100}$/.test(value)))throw Error();const remaining=(Date.parse(data.expires_at)-Date.now())/1000;if(!Number.isFinite(remaining)||remaining<=0)throw Error();
   const response=redirect(config.origin,destination),age=Math.min(86400,Math.floor(remaining));for(const [name,value] of [[names.session,data.session],[names.csrf,data.csrf]])response.headers.append('Set-Cookie',cookie(name!,value!,config.origin,age));response.headers.append('Set-Cookie',cookie(names.login,'',config.origin,0));response.headers.append('Set-Cookie',cookie(returnName,'',config.origin,0));return response;
  }
  const session=readCookie(request,names.session),csrf=readCookie(request,names.csrf);
  if(session&&csrf){const result=await send(new URL('/v1/auth/logout',config.base),{method:'POST',redirect:'error',cache:'no-store',headers:{Authorization:`Bearer ${config.token}`,'Content-Type':'application/json'},body:JSON.stringify({session,csrf}),signal:AbortSignal.timeout(15000)});if(!result.ok&&result.status!==401)return redirect(config.origin,'/account?error=sign-out');}
  const response=redirect(config.origin,'/sign-in?signed_out=1');for(const name of [...Object.values(names),returnName])response.headers.append('Set-Cookie',cookie(name,'',config.origin,0));return response;
 }catch(error){if(action==='sign-out')return redirect(config.origin,'/account?error=sign-out');const response=redirect(config.origin,`/sign-in?error=${error instanceof LoginFailure?error.reason:'unavailable'}&returnTo=${encodeURIComponent(destination)}`);response.headers.append('Set-Cookie',cookie(names.login,'',config.origin,0));response.headers.append('Set-Cookie',cookie(returnName,'',config.origin,0));return response;}
}
