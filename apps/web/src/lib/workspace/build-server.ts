import 'server-only';
import {createBackendClient} from '@f01/api-client';
import {configuration,sameOrigin,input,fail,object} from '../projects/server.ts';
import {backendCredentials,SessionUnavailable} from '../auth/session.ts';
import {uuid} from './contracts.ts';
export async function handleBuild(request:Request,projectId:string,segments:string[],env:Record<string,string|undefined>,send:typeof fetch=fetch){
 if(!uuid.test(projectId))return fail('NOT_FOUND',404);
 const [id,action]=segments;
 if(segments.length>2||id&&!uuid.test(id)||action&&!['cancel','retry'].includes(action))return fail('NOT_FOUND',404);
 const write=request.method==='POST';
 if(!['GET','POST'].includes(request.method)||action&&!write||id&&!action&&write)return fail('REQUEST_FORBIDDEN',405);
 let config:ReturnType<typeof configuration>;try{config=configuration(env);}catch{return fail('PROJECTS_NOT_CONFIGURED',503);}
 if(write&&!sameOrigin(request,config.origin,config.local))return fail('REQUEST_FORBIDDEN',403);
 try{
  const actor=await backendCredentials(request,config,send),client=createBackendClient({baseUrl:config.base.origin,bearerToken:actor.token,headers:actor.headers,fetch:send});
  const path={project_id:projectId},runPath={...path,run_id:id!},signal=AbortSignal.any([request.signal,AbortSignal.timeout(20000)]);
  let result;
  if(write){
   const key=request.headers.get('idempotency-key');
   if(action!=='cancel'&&(!key||!/^[A-Za-z0-9._:-]{1,200}$/.test(key)))return fail('VALIDATION_ERROR',422);
   let body:unknown;try{body=await input(request);}catch{return fail('VALIDATION_ERROR',422);}
   if(!object(body))return fail('VALIDATION_ERROR',422);
   if(!id){
    if(Object.keys(body).length!==1||typeof body.proposal_id!=='string'||!uuid.test(body.proposal_id))return fail('VALIDATION_ERROR',422);
    result=await client.POST('/v1/projects/{project_id}/builds',{params:{path,header:{'idempotency-key':key!}},body:{proposal_id:body.proposal_id},signal});
   }else{
    if(Object.keys(body).length)return fail('VALIDATION_ERROR',422);
    result=action==='cancel'?await client.POST('/v1/projects/{project_id}/builds/{run_id}/cancel',{params:{path:runPath},signal}):await client.POST('/v1/projects/{project_id}/builds/{run_id}/retry',{params:{path:runPath,header:{'idempotency-key':key!}},signal});
   }
  }else result=id?await client.GET('/v1/projects/{project_id}/builds/{run_id}',{params:{path:runPath},signal}):await client.GET('/v1/projects/{project_id}/builds',{params:{path},signal});
  if(!result.response.ok){const code=object(result.error)&&object(result.error.error)?String(result.error.error.code):'SERVICE_UNAVAILABLE';return Response.json({error:{code,message:'The build command could not complete. Inspect current context and try again.'}},{status:result.response.status,headers:{'Cache-Control':'no-store'}});}
  const value=JSON.stringify(result.data);if(!value||value.length>2*1024*1024||value.includes(actor.token)||value.includes(config.token))return fail('INTERNAL_ERROR',502);
  return Response.json(result.data,{status:result.response.status,headers:{'Cache-Control':'no-store'}});
 }catch(error){return fail(error instanceof SessionUnavailable&&error.status===401?'AUTHENTICATION_REQUIRED':'SERVICE_UNAVAILABLE',error instanceof SessionUnavailable?error.status:503);}
}
export async function handleSource(request:Request,projectId:string,versionId:string,env:Record<string,string|undefined>,send:typeof fetch=fetch){
 if(request.method!=='GET')return fail('REQUEST_FORBIDDEN',405);if(!uuid.test(projectId)||!uuid.test(versionId))return fail('NOT_FOUND',404);
 try{const config=configuration(env),actor=await backendCredentials(request,config,send),client=createBackendClient({baseUrl:config.base.origin,bearerToken:actor.token,headers:actor.headers,fetch:send});
  const result=await client.GET('/v1/projects/{project_id}/versions/{version_id}/source',{params:{path:{project_id:projectId,version_id:versionId}},signal:AbortSignal.any([request.signal,AbortSignal.timeout(20000)])});
  if(!result.response.ok)return fail(result.response.status===404?'NOT_FOUND':'SERVICE_UNAVAILABLE',result.response.status);
  const value=JSON.stringify(result.data);if(!value||value.length>2*1024*1024||value.includes(actor.token)||value.includes(config.token))return fail('INTERNAL_ERROR',502);
  return Response.json(result.data,{headers:{'Cache-Control':'no-store'}});
 }catch{return fail('SERVICE_UNAVAILABLE',503);}
}
