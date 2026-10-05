import {uuid} from './contracts.ts';
export type BuildReceipt={key:string;path:string;body:{proposal_id:string}|Record<string,never>;created?:number};
export function buildReceipt(value:unknown,project:string):BuildReceipt|null{
 if(!value||typeof value!=='object'||!uuid.test(project))return null;
 const v=value as BuildReceipt;if(typeof v.key!=='string'||!uuid.test(v.key)||typeof v.path!=='string'||!v.body||typeof v.body!=='object'||Array.isArray(v.body))return null;
 if(v.created!==undefined&&(!Number.isFinite(v.created)||v.created>Date.now()||v.created<0))return null;
 const base=`/projects/${project}/builds`;
 if(v.path===base)return Object.keys(v.body).length===1&&'proposal_id' in v.body&&typeof v.body.proposal_id==='string'&&uuid.test(v.body.proposal_id)?v:null;
 const suffix=v.path.slice(base.length);return v.path.startsWith(base)&&/^\/[a-f0-9-]{36}\/(cancel|retry)$/.test(suffix)&&Object.keys(v.body).length===0?v:null;
}
export function buildReceiptExpired(receipt: BuildReceipt): boolean {
 return receipt.created === undefined || Date.now() - receipt.created >= 86400000;
}
