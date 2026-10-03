import 'server-only';
import {createBackendClient} from '@f01/api-client';
import {configuration,sameOrigin,input,fail,object} from '../projects/server.ts';
import {errors} from '../projects/contracts.ts';
import {planningErrors} from '../planning/contracts.ts';
import {backendCredentials,SessionUnavailable} from '../auth/session.ts';
import {uuid} from './contracts.ts';
export async function handleContextPlanning(request:Request,projectId:string,segments:string[],env:Record<string,string|undefined>,send:typeof fetch=fetch){
 if(!uuid.test(projectId))return fail('NOT_FOUND',404);
 const [resource,id,action]=segments;
 const valid=segments.length===1&&['attempts','proposals'].includes(resource??'') || segments.length===2&&resource==='attempts'&&uuid.test(id??'') || segments.length===3&&uuid.test(id??'')&&((resource==='attempts'&&action==='cancel')||(resource==='proposals'&&action==='review'));
 if(!valid)return fail('NOT_FOUND',404);
 const write=resource==='attempts'&&segments.length===1||segments.length===3;
 if(request.method!==(write?'POST':'GET'))return fail('REQUEST_FORBIDDEN',405);
 let config:ReturnType<typeof configuration>;try{config=configuration(env);}catch{return fail('PROJECTS_NOT_CONFIGURED',503);}
 if(write&&!sameOrigin(request,config.origin,config.local))return fail('REQUEST_FORBIDDEN',403);
 try{
  const actor=await backendCredentials(request,config,send),client=createBackendClient({baseUrl:config.base.origin,bearerToken:actor.token,headers:actor.headers,fetch:send});
  const path={project_id:projectId},signal=AbortSignal.any([request.signal,AbortSignal.timeout(20000)]);
  let result;
  if(resource==='attempts'&&segments.length===1){
   let body:unknown;try{body=await input(request);}catch{return fail('VALIDATION_ERROR',422);}const key=request.headers.get('idempotency-key');
   if(!object(body)||Object.keys(body).some(k=>!['kind','request_id','base_brain_revision_id','base_version_id'].includes(k))||!['initial','change'].includes(String(body.kind))||typeof body.request_id!=='string'||!uuid.test(body.request_id)||typeof body.base_brain_revision_id!=='string'||!uuid.test(body.base_brain_revision_id)||!(body.base_version_id===null||typeof body.base_version_id==='string'&&uuid.test(body.base_version_id))||!key||!/^[A-Za-z0-9._:-]{1,200}$/.test(key))return fail('VALIDATION_ERROR',422);
   result=await client.POST('/v1/projects/{project_id}/planning/attempts',{params:{path,header:{'idempotency-key':key}},body:{kind:body.kind as 'initial'|'change',request_id:body.request_id,base_brain_revision_id:body.base_brain_revision_id,base_version_id:body.base_version_id},signal});
  }else if(action==='cancel')result=await client.POST('/v1/projects/{project_id}/planning/attempts/{attempt_id}/cancel',{params:{path:{...path,attempt_id:id!}},signal});
  else if(action==='review')result=await client.POST('/v1/projects/{project_id}/planning/proposals/{proposal_id}/review',{params:{path:{...path,proposal_id:id!}},signal});
  else if(resource==='attempts')result=await client.GET('/v1/projects/{project_id}/planning/attempts/{attempt_id}',{params:{path:{...path,attempt_id:id!}},signal});
  else result=await client.GET('/v1/projects/{project_id}/planning/proposals',{params:{path},signal});
  if(!result.response.ok){const code=object(result.error)&&object(result.error.error)?String(result.error.error.code):'INTERNAL_ERROR';if(code in planningErrors){const value=planningErrors[code as keyof typeof planningErrors];return Response.json({error:{code,message:value.message}},{status:result.response.status,headers:{'Cache-Control':'no-store'}});}return fail(code in errors?code:'INTERNAL_ERROR',result.response.status);}
  const value=JSON.stringify(result.data);if(!value||value.length>2*1024*1024||value.includes(actor.token)||value.includes(config.token))return fail('INTERNAL_ERROR',502);
  return Response.json(result.data,{status:result.response.status,headers:{'Cache-Control':'no-store'}});
 }catch(error){return fail(error instanceof SessionUnavailable&&error.status===401?'AUTHENTICATION_REQUIRED':'SERVICE_UNAVAILABLE',error instanceof SessionUnavailable?error.status:503);}
}
