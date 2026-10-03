import {handleContextPlanning} from '@/lib/workspace/planning-server';
export const dynamic='force-dynamic';
export const runtime='nodejs';
async function handle(request:Request,{params}:{params:Promise<{projectId:string;segments:string[]}>}){const values=await params;return handleContextPlanning(request,values.projectId,values.segments,process.env);}
export const GET=handle;
export const POST=handle;
