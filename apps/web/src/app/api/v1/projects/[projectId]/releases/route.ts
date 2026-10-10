import {handleRelease} from '@/lib/workspace/releases-server';
export async function GET(request:Request,{params}:{params:Promise<{projectId:string}>}){return handleRelease(request,(await params).projectId,'releases',[],process.env);}
export async function POST(request:Request,{params}:{params:Promise<{projectId:string}>}){return handleRelease(request,(await params).projectId,'releases',[],process.env);}
