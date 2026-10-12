const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export type IntentDraft={project:string;owner:string;brain:string;version:string|null;text:string};
export const intentKey=(project:string)=>`f01.workspace-intent.v1.${project}`;
export function readIntentDraft(storage:Pick<Storage,'getItem'>,project:string,owner:string):IntentDraft|null{
 try{const value=JSON.parse(storage.getItem(intentKey(project))??'null');if(value&&value.project===project&&value.owner===owner&&uuid.test(value.project)&&uuid.test(value.owner)&&uuid.test(value.brain)&&(value.version===null||uuid.test(value.version))&&typeof value.text==='string'&&Array.from(value.text).length<=10000)return value;}catch{}return null;
}
export function saveIntentDraft(storage:Pick<Storage,'setItem'>,draft:IntentDraft):boolean{
 try{storage.setItem(intentKey(draft.project),JSON.stringify(draft));return true;}catch{return false;}
}
