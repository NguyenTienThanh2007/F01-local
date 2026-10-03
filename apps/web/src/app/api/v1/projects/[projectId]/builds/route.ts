import {handleBuild} from '@/lib/workspace/build-server';
export const dynamic='force-dynamic';
async function handle(request:Request,{params}:{params:Promise<{projectId:string}>}){return handleBuild(request,(await params).projectId,[],process.env);}
export const GET=handle;
export const POST=handle;
