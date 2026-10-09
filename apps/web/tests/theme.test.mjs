import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {readIntentDraft,saveIntentDraft,intentKey} from '../src/lib/workspace/intent-draft.ts';
const source=readFileSync(new URL('../public/theme-init.js',import.meta.url),'utf8');
function boot({stored=null,dark=false,blocked=false}={}){
 const callbacks={},mediaCallbacks={},values=new Map(stored===null?[]:[['f01.theme.v1',stored]]),root={dataset:{},style:{}},media={matches:dark,addEventListener:(type,fn)=>{mediaCallbacks[type]=fn;}};
 const storage={getItem:key=>{if(blocked)throw Error('blocked');return values.get(key)??null;},setItem:(key,value)=>{if(blocked)throw Error('blocked');values.set(key,value);}};
 const window={matchMedia:()=>media,dispatchEvent:()=>{},addEventListener:(type,fn)=>{callbacks[type]=fn;}};
 vm.runInNewContext(source,{window,document:{documentElement:root},localStorage:storage,Event:class{constructor(type){this.type=type;}}});return {window,root,values,media,mediaCallbacks,callbacks};
}
test('new users default to light even on a dark system; stored preferences apply synchronously',()=>{
 assert.equal(boot({dark:true}).root.dataset.theme,'light');assert.equal(boot({stored:'dark'}).root.dataset.theme,'dark');assert.equal(boot({stored:'system',dark:true}).root.dataset.theme,'dark');assert.equal(boot({stored:'invalid',dark:true}).root.dataset.theme,'light');
});
test('only System follows OS changes; explicit selection persists and supports cross-tab updates',()=>{
 const b=boot({stored:'system'});b.media.matches=true;b.mediaCallbacks.change();assert.equal(b.root.dataset.theme,'dark');b.window.f01Theme.set('light');b.mediaCallbacks.change();assert.equal(b.root.dataset.theme,'light');assert.equal(b.values.get('f01.theme.v1'),'light');b.callbacks.storage({key:'f01.theme.v1',newValue:'dark'});assert.equal(b.window.f01Theme.get(),'dark');b.callbacks.storage({key:null,newValue:null});assert.equal(b.root.dataset.theme,'light');
});
test('blocked storage still supports in-page dark/system preferences without an exception',()=>{
 const b=boot({blocked:true});b.window.f01Theme.set('dark');assert.equal(b.root.style.colorScheme,'dark');b.window.f01Theme.set('system');b.media.matches=true;b.mediaCallbacks.change();assert.equal(b.root.dataset.theme,'dark');
});
const project='00000000-0000-4000-8000-000000000001',owner='00000000-0000-4000-8000-000000000002',brain='00000000-0000-4000-8000-000000000003';
test('conversational draft handoff is project/owner bound and retains its exact review context',()=>{
 const values=new Map(),storage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};const draft={project,owner,brain,version:null,text:'Add a priority filter and keep the current layout.'};assert.equal(saveIntentDraft(storage,draft),true);assert.deepEqual(readIntentDraft(storage,project,owner),draft);assert.equal(readIntentDraft(storage,project,brain),null);assert.equal(readIntentDraft(storage,owner,owner),null);values.set(intentKey(project),JSON.stringify({...draft,brain:'invalid'}));assert.equal(readIntentDraft(storage,project,owner),null);assert.equal(saveIntentDraft({setItem:()=>{throw Error('quota');}},draft),false);
});
