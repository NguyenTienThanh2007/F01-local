// Frontend recovery/readonly contract checks; no Docker or provider success claim.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {launchTestBrowser,stopBrowserServer} from './browser-process.mjs';
import * as f from './build-observation-fixtures.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
test('owned conversation restores before editing, retains unsent text and preserves historical readonly',{timeout:60000},async()=>{
 const probe=createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));const base=`http://127.0.0.1:${port}`,path=`/projects/${f.ids.project}`;
 const env={...process.env,APP_ENV:'test',AUTH_MODE:'development',EXECUTION_MODE:'real',DEV_API_TOKEN:'synthetic-conversation-token-12345678901234567890',API_INTERNAL_URL:'http://127.0.0.1:9',NEXT_PUBLIC_APP_URL:base};delete env.OPENAI_API_KEY;delete env.F01_VERCEL_TOKEN;
 const server=spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{cwd:root,env,stdio:'ignore'});let browser,releaseSession=()=>{};
 try{
  let ready=false;for(let attempt=0;attempt<100;attempt++){if(await fetch(base).then(r=>r.ok).catch(()=>false)){ready=true;break;}await delay(100);}assert.ok(ready);
  browser=await launchTestBrowser({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const saved='Add a saved priority filter without changing the existing dashboard.',storageKey=`f01.workspace-intent.v1.${f.ids.project}`;
  await page.addInitScript(({key,project,owner,text})=>{if(!sessionStorage.getItem(key))sessionStorage.setItem(key,JSON.stringify({project,owner,brain:owner,version:null,text}));},{key:storageKey,project:f.ids.project,owner:f.ids.brain,text:saved});
  let owner=f.ids.brain,held=true,snapshot=f.snapshot(),writes=0;const pending=new Promise(resolve=>{releaseSession=resolve;});
  const version=f.version({preview_descriptor:{kind:'isolated',url:`http://localhost:3031/p/${f.ids.version}/${'a'.repeat(43)}/`,expires_at:new Date(Date.now()+3600000).toISOString()}});
  await page.route('http://localhost:3031/p/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en"><title>Contract preview</title><main>Controlled rendering fixture</main></html>'}));
  await page.route('**/api/v1/**',async route=>{
   const resource=new URL(route.request().url()).pathname.replace('/api/v1','');if(route.request().method()!=='GET')writes++;
   if(resource==='/session'&&held)await pending;
   let data=resource==='/session'?{principal:{id:owner,display_name:'Contract owner',identity_mode:'development'},capabilities:{execution_mode:'real',real_generation:true}}:resource.endsWith('/workspace')?snapshot:resource.endsWith('/releases')?f.releases():resource.endsWith('/versions/'+f.ids.version)?version:{items:[],next_cursor:null};
   if(resource.endsWith('/events/stream'))return route.abort('failed');
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto(base+path);const input=page.getByRole('textbox',{name:'What should change?',exact:true});await input.waitFor();assert.equal(await input.isDisabled(),true,'Do not accept typing until the owned saved draft is restored.');held=false;releaseSession();await page.waitForFunction(expected=>document.querySelector('#workspace-intent')?.value===expected,saved);assert.equal(await input.isDisabled(),false);
  await input.fill('A partial draft');await page.reload();await page.waitForFunction(()=>document.querySelector('#workspace-intent')?.value==='A partial draft');assert.equal(await input.inputValue(),'A partial draft','Unsubmitted text survives reload.');
  const draft=await page.evaluate(key=>JSON.parse(sessionStorage.getItem(key)),storageKey);assert.equal(draft.owner,f.ids.brain);assert.equal(draft.brain,f.ids.brain);assert.equal(draft.version,null);
  await input.fill(saved);snapshot=f.snapshot({current_version:version,project:{...f.snapshot().project,current_version_id:version.id,lifecycle:'live'}});await page.goto(base+path+'?version='+version.id);await page.getByText('Historical preview is read-only.').waitFor();await page.waitForFunction(expected=>document.querySelector('#workspace-intent')?.value===expected,saved);assert.equal(await input.isDisabled(),true);assert.equal(await page.getByRole('button',{name:'Review this change ↗',exact:true}).isDisabled(),true);const retained=await page.evaluate(key=>sessionStorage.getItem(key),storageKey);await page.evaluate(key=>sessionStorage.removeItem(key),storageKey);await page.locator('.conversation-composer').evaluate(form=>form.requestSubmit());assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),storageKey),null,'Historical submission does not stage a new change even when its text is valid.');await page.evaluate(({key,value})=>sessionStorage.setItem(key,value),{key:storageKey,value:retained});assert.match(page.url(),/\?version=/);assert.equal(writes,0,'Historical inspection starts no command.');
  owner=f.ids.candidate;await page.goto(base+path);await page.getByText('This workspace belongs to another account.').waitFor();assert.equal(await input.isDisabled(),true);assert.equal(await input.inputValue(),'','An unrelated account does not receive the owned draft.');assert.equal(writes,0);
 }finally{releaseSession();await browser?.close();await stopBrowserServer(server);}
});
