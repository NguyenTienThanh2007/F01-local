import {handleProjectsRequest} from '@/lib/projects/server';
export const dynamic='force-dynamic';
export function GET(request:Request){return handleProjectsRequest(request,'usage',undefined,process.env);}
