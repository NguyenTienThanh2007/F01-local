import {handleProjectsRequest} from '@/lib/projects/server';
export const dynamic='force-dynamic';
export function GET(request:Request){return handleProjectsRequest(request,'account',undefined,process.env);}
export function PATCH(request:Request){return handleProjectsRequest(request,'account',undefined,process.env);}
