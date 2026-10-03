import {handleBuild} from '@/lib/workspace/build-server';
export const dynamic='force-dynamic';
async function handle(request:Request,{params}:{params:Promise<{projectId:string;segments:string[]}>}){const p=await params;return handleBuild(request,p.projectId,p.segments,process.env);}
export const GET=handle;
export const POST=handle;
