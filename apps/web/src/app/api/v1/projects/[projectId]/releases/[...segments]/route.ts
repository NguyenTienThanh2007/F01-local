import {handleRelease} from '@/lib/workspace/releases-server';
export async function POST(request:Request,{params}:{params:Promise<{projectId:string;segments:string[]}>}){const p=await params;return handleRelease(request,p.projectId,'releases',p.segments,process.env);}
