import {uuid} from './contracts.ts';
export type BuildReceipt={key:string;path:string;body:{proposal_id:string}|Record<string,never>};
export function buildReceipt(value:unknown,project:string):BuildReceipt|null{
 if(!value||typeof value!=='object'||!uuid.test(project))return null;
 const v=value as BuildReceipt;if(typeof v.key!=='string'||!uuid.test(v.key)||typeof v.path!=='string'||!v.body||typeof v.body!=='object'||Array.isArray(v.body))return null;
 const base=`/projects/${project}/builds`;
 if(v.path===base)return Object.keys(v.body).length===1&&'proposal_id' in v.body&&typeof v.body.proposal_id==='string'&&uuid.test(v.body.proposal_id)?v:null;
 const suffix=v.path.slice(base.length);return v.path.startsWith(base)&&/^\/[a-f0-9-]{36}\/(cancel|retry)$/.test(suffix)&&Object.keys(v.body).length===0?v:null;
}
