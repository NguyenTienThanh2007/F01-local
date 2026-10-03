import {handleSource} from '@/lib/workspace/build-server';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{projectId:string;versionId:string}>}){const p=await params;return handleSource(request,p.projectId,p.versionId,process.env);}
