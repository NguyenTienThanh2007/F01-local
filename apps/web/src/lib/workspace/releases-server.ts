import 'server-only';
import {createBackendClient} from '@f01/api-client';
import type {components} from '@f01/api-client/schema';
import {configuration,sameOrigin,input,fail,object} from '../projects/server.ts';
import {backendCredentials,SessionUnavailable} from '../auth/session.ts';
import {uuid} from './contracts.ts';
export async function handleRelease(request:Request,projectId:string,kind:'releases'|'release-artifacts'|'release-target',segments:string[],env:Record<string,string|undefined>,send:typeof fetch=fetch){
 if(!uuid.test(projectId)||segments.length>2||segments.length===1||segments.length===2&&(!uuid.test(segments[0]!)||segments[1]!=='cancel')||kind!=='releases'&&segments.length)return fail('NOT_FOUND',404);
 const write=request.method==='POST';
 if(!['GET','POST'].includes(request.method)||!write&&(kind!=='releases'||segments.length))return fail('REQUEST_FORBIDDEN',405);
 let config:ReturnType<typeof configuration>;try{config=configuration(env);}catch{return fail('PROJECTS_NOT_CONFIGURED',503);}
 if(write&&!sameOrigin(request,config.origin,config.local))return fail('REQUEST_FORBIDDEN',403);
 try{
  const actor=await backendCredentials(request,config,send),client=createBackendClient({baseUrl:config.base.origin,bearerToken:actor.token,headers:actor.headers,fetch:send});
  const path={project_id:projectId},signal=AbortSignal.any([request.signal,AbortSignal.timeout(20000)]);
  let result;
  if(write){
   let body:unknown;try{body=await input(request);}catch{return fail('VALIDATION_ERROR',422);}
   if(!object(body))return fail('VALIDATION_ERROR',422);
   const key=request.headers.get('idempotency-key');
   if(!segments.length&&(!key||!/^[A-Za-z0-9._:-]{1,200}$/.test(key)))return fail('VALIDATION_ERROR',422);
   if(segments.length){
    if(Object.keys(body).length)return fail('VALIDATION_ERROR',422);
    result=await client.POST('/v1/projects/{project_id}/releases/{release_id}/cancel',{params:{path:{...path,release_id:segments[0]!}},signal});
   }else if(kind==='release-target'){
    if(Object.keys(body).length!==2||!['expected_version_id','expected_brain_revision_id'].every(k=>typeof body[k]==='string'&&uuid.test(body[k])))return fail('VALIDATION_ERROR',422);
    result=await client.POST('/v1/projects/{project_id}/release-target',{params:{path,header:{'idempotency-key':key!}},body:body as components['schemas']['SetupReleaseTarget'],signal});
   }else if(kind==='release-artifacts'){
    if(Object.keys(body).length!==3||!['version_id','configuration_id','expected_brain_revision_id'].every(k=>typeof body[k]==='string'&&uuid.test(body[k])))return fail('VALIDATION_ERROR',422);
    result=await client.POST('/v1/projects/{project_id}/release-artifacts',{params:{path,header:{'idempotency-key':key!}},body:body as components['schemas']['PrepareRelease'],signal});
   }else{
    const ids=['artifact_id','configuration_id','expected_brain_revision_id','expected_version_id'];
    if(Object.keys(body).length!==6||!ids.every(k=>typeof body[k]==='string'&&uuid.test(body[k]))||!(body.expected_production_release_id===null||typeof body.expected_production_release_id==='string'&&uuid.test(body.expected_production_release_id))||!Number.isSafeInteger(body.expected_target_generation)||Number(body.expected_target_generation)<0)return fail('VALIDATION_ERROR',422);
    result=await client.POST('/v1/projects/{project_id}/releases',{params:{path,header:{'idempotency-key':key!}},body:body as components['schemas']['PromoteRelease'],signal});
   }
  }else result=await client.GET('/v1/projects/{project_id}/releases',{params:{path},signal});
  if(!result.response.ok){const code=object(result.error)&&object(result.error.error)?String(result.error.error.code):'SERVICE_UNAVAILABLE';return Response.json({error:{code,message:'The release command could not complete. Review saved release status and current context.'}},{status:result.response.status,headers:{'Cache-Control':'no-store'}});}
  const raw=JSON.stringify(result.data);if(!raw||raw.length>2*1024*1024||raw.includes(actor.token)||raw.includes(config.token))return fail('INTERNAL_ERROR',502);
  return Response.json(result.data,{status:result.response.status,headers:{'Cache-Control':'no-store'}});
 }catch(error){return fail(error instanceof SessionUnavailable&&error.status===401?'AUTHENTICATION_REQUIRED':'SERVICE_UNAVAILABLE',error instanceof SessionUnavailable?error.status:503);}
}
