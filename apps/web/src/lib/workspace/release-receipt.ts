import {uuid} from './contracts.ts';
export type ReleaseReceipt={key:string;path:string;body:Record<string,string|number|null>;created:number};
export function releaseReceipt(value:unknown,id:string):ReleaseReceipt|null{
 if(!value||typeof value!=='object')return null;
 const receipt=value as ReleaseReceipt;
 if(typeof receipt.key!=='string'||!/^[A-Za-z0-9._:-]{1,200}$/.test(receipt.key)||typeof receipt.created!=='number'||!Number.isFinite(receipt.created)||receipt.created<=0||receipt.created>Date.now()+60000||!receipt.body||typeof receipt.body!=='object'||Array.isArray(receipt.body))return null;
 const keys=Object.keys(receipt.body).sort().join(','),preparing=receipt.path===`/projects/${id}/release-artifacts`||new RegExp(`^/projects/${id}/release-artifacts/[0-9a-f-]{36}/retry$`,'i').test(receipt.path),deploying=receipt.path===`/projects/${id}/releases`||new RegExp(`^/projects/${id}/releases/[0-9a-f-]{36}/retry$`,'i').test(receipt.path),settingUp=receipt.path===`/projects/${id}/release-target`;
 if(preparing&&keys!=='configuration_id,expected_brain_revision_id,version_id'||deploying&&keys!=='artifact_id,configuration_id,expected_brain_revision_id,expected_production_release_id,expected_target_generation,expected_version_id'||settingUp&&keys!=='expected_brain_revision_id,expected_version_id'||!preparing&&!deploying&&!settingUp)return null;
 for(const [key,item] of Object.entries(receipt.body)){
  if(key==='expected_target_generation'){if(!Number.isSafeInteger(item)||Number(item)<0)return null;}
  else if(key==='expected_production_release_id'&&item===null)continue;
  else if(typeof item!=='string'||!uuid.test(item))return null;
 }
 return receipt;
}
export function releaseReceiptExpired(receipt:ReleaseReceipt){return Date.now()-receipt.created>=24*60*60*1000-60000;}
export function productionURL(value:string|null|undefined):string|null{
 if(!value)return null;
 try{const url=new URL(value);if((value===url.origin||value===url.origin+'/')&&url.protocol==='https:'&&/^[a-z0-9][a-z0-9-]{0,100}\.vercel\.app$/.test(url.hostname)&&url.host===url.hostname&&!url.username&&!url.password&&!url.search&&!url.hash&&url.pathname==='/')return url.origin;}catch{}
 return null;
}
