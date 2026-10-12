import {handleRelease} from '@/lib/workspace/releases-server';
export async function POST(request:Request,{params}:{params:Promise<{projectId:string}>}){return handleRelease(request,(await params).projectId,'release-artifacts',[],process.env);}
