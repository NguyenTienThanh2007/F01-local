import {stopBrowserServer} from './browser-process.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {mkdir,readFile} from 'node:fs/promises';
import {setTimeout as delay} from 'node:timers/promises';
import {chromium} from 'playwright';

const root=fileURLToPath(new URL('../',import.meta.url));
async function until(check){for(let i=0;i<120;i++){if(await check().catch(()=>false))return;await delay(100);}throw Error('Expected core journey state not reached');}
test('UX0 signed-in real-mode commands (no Docker execution)',{timeout:180000},async t=>{
 const api=process.env.M5_API_URL,port=process.env.P2A_WEB_PORT,gateway=process.env.AUTH_GATEWAY_TOKEN;
 assert.ok(api&&port&&gateway,'Run the disposable UX0 browser harness.');
 const base=`http://127.0.0.1:${port}`,env={...process.env,APP_ENV:'test',AUTH_MODE:'oidc',EXECUTION_MODE:'real',AUTH_GATEWAY_TOKEN:gateway,API_INTERNAL_URL:api,NEXT_PUBLIC_APP_URL:base};
 delete env.OPENAI_API_KEY;
 const server=spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',port],{cwd:root,env,stdio:'ignore'});
 let browser;
 const evidence=`${root}/test-results/ux0`;await mkdir(evidence,{recursive:true});
 async function signIn(page){await page.goto(`${base}/sign-in`);await page.getByRole('button',{name:'Sign in securely'}).click();await page.getByRole('button',{name:'Sign in as test owner A'}).click();await page.waitForURL(`${base}/projects`);}
 async function read(page,path){return page.evaluate(async path=>{const r=await fetch(`/api/v1${path}`);return {status:r.status,data:await r.json()};},path);}
 async function seed(page,title){const r=await page.evaluate(async title=>{const response=await fetch('/api/v1/projects',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({title,brief:'Build a browser-only dashboard with leads and private notes.'})});return {status:response.status,data:await response.json()};},title);assert.equal(r.status,201);assert.equal(r.data.execution_mode,'real');assert.equal(r.data.run_id,null);return r.data.project.id;}
 async function scenario(name,fn){await t.test(name,async()=>{const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));try{await signIn(page);await fn(page);assert.deepEqual(errors,[]);}catch(e){await page.screenshot({path:`${evidence}/${name.split(' ')[0]}-failure.png`,fullPage:true});throw e;}finally{await page.close();}});}
 try{
  await until(async()=> (await fetch(base)).ok);browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
  await scenario('creation resolves a lost real response with the same receipt after reload',async page=>{
   const commands=[];let lose=true;
   await page.route('**/api/v1/projects',async route=>{if(route.request().method()!=='POST')return route.continue();commands.push({key:route.request().headers()['idempotency-key'],body:route.request().postData()});if(lose){lose=false;await route.fetch();await route.abort('failed');}else await route.continue();});
   await page.goto(`${base}/projects/new`);await page.getByRole('textbox',{name:/Project title/}).fill('UX0 real project');await page.getByRole('textbox',{name:'Product brief'}).fill('Build a browser-only dashboard for a small property agency.');
   await page.locator('form.saved-project-form').evaluate(form=>{form.requestSubmit();form.requestSubmit();});
   await page.getByRole('button',{name:'Retry project creation'}).waitFor();assert.equal(commands.length,1);await page.reload();await page.getByRole('button',{name:'Retry project creation'}).click();await page.waitForURL(/\/projects\/[0-9a-f-]{36}$/,{timeout:10000});
   assert.equal(commands.length,2);assert.deepEqual(commands[0],commands[1]);const id=new URL(page.url()).pathname.split('/').at(-1);const snapshot=(await read(page,`/projects/${id}/workspace`)).data;assert.equal(snapshot.active_run,null);assert.equal(snapshot.current_version,null);assert.equal((await read(page,'/projects?q=UX0%20real%20project')).data.items.length,1);await page.reload();await page.getByRole('heading',{name:'UX0 real project',exact:true}).waitFor();
  });
  await scenario('creation recovery cannot replay another account’s saved brief',async page=>{
   let lost=false;
   await page.route('**/api/v1/projects',async route=>{if(!lost&&route.request().method()==='POST'){lost=true;await route.fetch();await route.abort('failed');}else await route.continue();});
   await page.goto(`${base}/projects/new`);await page.getByRole('textbox',{name:/Project title/}).fill('Account A private recovery');await page.getByRole('textbox',{name:'Product brief'}).fill('Build a private browser-only notes tool for account A.');await page.getByRole('button',{name:'Create project',exact:true}).click();await page.getByRole('button',{name:'Retry project creation'}).waitFor();
   await page.goto(`${base}/account`);await page.getByRole('button',{name:'Sign out'}).click();await page.goto(`${base}/sign-in`);await page.getByRole('button',{name:'Sign in securely'}).click();await page.getByRole('button',{name:'Sign in as test owner B'}).click();await page.waitForURL(`${base}/projects`);await page.goto(`${base}/projects/new`);
   await page.getByRole('link',{name:'Review the account for this saved command'}).waitFor();assert.equal(await page.getByRole('button',{name:'Retry project creation'}).count(),0);assert.equal(await page.getByRole('textbox',{name:'Product brief'}).inputValue(),'');
   assert.equal((await read(page,'/projects?q=Account%20A%20private%20recovery')).data.items.length,0,'Account B must never receive account A’s unresolved creation.');await signIn(page);await page.goto(`${base}/projects/new`);await page.getByRole('button',{name:'Retry project creation'}).click();await page.waitForURL(/\/projects\/[0-9a-f-]{36}$/);assert.equal((await read(page,'/projects?q=Account%20A%20private%20recovery')).data.items.length,1);
  });
  await scenario('build submits JSON and recovers one queued run after response loss',async page=>{
   const id=await seed(page,'UX0 build command');await page.goto(`${base}/projects/${id}/planning`);await page.getByRole('button',{name:'Plan from original brief'}).click();await page.getByRole('heading',{name:'Contextual CRM proposal',exact:true}).waitFor();await page.getByRole('button',{name:'Approve this plan'}).click();await page.getByText('Plan approved. Building has not started.',{exact:true}).waitFor();await page.goto(`${base}/projects/${id}`);
   const commands=[];let lose=true;
   await page.route('**/api/v1/projects/*/builds',async route=>{if(route.request().method()!=='POST')return route.continue();commands.push({key:route.request().headers()['idempotency-key'],body:route.request().postData(),type:route.request().headers()['content-type']});if(lose){lose=false;await route.fetch();await route.abort('failed');}else await route.continue();});
   await page.getByRole('button',{name:'Build reviewed plan'}).click();await until(async()=> await page.getByRole('button',{name:'Resolve saved build command'}).isEnabled());const before=await read(page,`/projects/${id}/builds`);assert.equal(before.data.items.length,1,'The JSON command must reach FastAPI and reserve a run.');assert.equal(before.data.items[0].run.status,'queued');
   await page.reload();await page.getByRole('button',{name:'Resolve saved build command'}).click();await until(async()=> !(await page.getByRole('button',{name:'Resolve saved build command'}).isVisible()));assert.equal(commands.length,2);assert.deepEqual(commands[0],commands[1]);assert.equal(commands[0].type,'application/json');assert.equal((await read(page,`/projects/${id}/builds`)).data.items.length,1);await page.getByRole('button',{name:'Cancel real build'}).click();await until(async()=> (await read(page,`/projects/${id}/builds`)).data.items[0].run.status==='canceled');
  });
  await scenario('storage restrictions preserve confirmed creation planning and build results',async page=>{
   await page.addInitScript(()=>{for(const method of ['getItem','setItem','removeItem'])Storage.prototype[method]=()=>{throw new DOMException('Storage blocked','SecurityError');};});
   await page.goto(`${base}/projects/new`);await page.getByRole('textbox',{name:/Project title/}).fill('UX0 blocked storage');await page.getByRole('textbox',{name:'Product brief'}).fill('Build a browser-only dashboard with property leads.');await page.getByRole('button',{name:'Create project',exact:true}).click();await page.waitForURL(/\/projects\/[0-9a-f-]{36}$/);const id=new URL(page.url()).pathname.split('/').at(-1);
   await page.goto(`${base}/projects/${id}/planning`);await page.getByRole('button',{name:'Plan from original brief'}).click();await page.getByRole('heading',{name:'Contextual CRM proposal',exact:true}).waitFor();await page.getByRole('button',{name:'Approve this plan'}).click();await page.getByRole('link',{name:'Continue to build'}).click();
   let sent=0;await page.route('**/api/v1/projects/*/builds',async route=>{if(route.request().method()==='POST')sent++;await route.continue();});
   const build=page.getByRole('button',{name:'Build reviewed plan'});await build.waitFor();await build.evaluate(button=>{button.click();button.click();});await page.getByRole('heading',{name:'Build queued',exact:true}).waitFor();assert.equal(sent,1);assert.equal((await read(page,`/projects/${id}/builds`)).data.items.length,1);assert.deepEqual(await page.getByRole('alert').filter({hasText:/unavailable|could not|failed|blocked/i}).allTextContents(),[]);
   for(const width of [375,768,1280,1440]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}px overflow`);if(process.env.M5_AXE_SCRIPT){await page.addScriptTag({content:await readFile(process.env.M5_AXE_SCRIPT,'utf8')});assert.deepEqual(await page.evaluate(async()=> (await axe.run(document,{iframes:false,runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id)),[],`${width}px accessibility`);}await page.screenshot({path:`${evidence}/queued-${width}.png`,fullPage:true});}
   await page.getByRole('button',{name:'Cancel real build'}).click();await until(async()=> (await read(page,`/projects/${id}/builds`)).data.items[0].run.status==='canceled');
  });
  await scenario('uncertain conflict retains a build receipt and expired recovery cannot redispatch',async page=>{
   const id=await seed(page,'UX0 uncertain build');await page.goto(`${base}/projects/${id}/planning`);await page.getByRole('button',{name:'Plan from original brief'}).click();await page.getByRole('heading',{name:'Contextual CRM proposal',exact:true}).waitFor();await page.getByRole('button',{name:'Approve this plan'}).click();await page.getByRole('link',{name:'Continue to build'}).click();
   let sends=0;await page.route('**/api/v1/projects/*/builds',async route=>{if(route.request().method()!=='POST')return route.continue();sends++;await route.fetch();await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:{code:'IDEMPOTENCY_IN_PROGRESS'}})});});
   await page.getByRole('button',{name:'Build reviewed plan'}).click();await until(async()=> await page.getByRole('button',{name:'Resolve saved build command'}).isEnabled());assert.equal(sends,1);assert.equal((await read(page,`/projects/${id}/builds`)).data.items.length,1);
   await page.evaluate(id=>{const name=`f01:build:${id}`,r=JSON.parse(sessionStorage.getItem(name));r.created=Date.now()-86400001;sessionStorage.setItem(name,JSON.stringify(r));},id);await page.reload();await page.getByRole('alert').filter({hasText:/safe recovery window/}).waitFor();assert.equal(await page.getByRole('button',{name:'Resolve saved build command'}).count(),0);assert.equal(await page.getByRole('button',{name:'Build reviewed plan'}).count(),0);assert.equal(sends,1);
  });
 }finally{console.info('Closing test browser');await browser?.close();console.info('Stopping test server');await stopBrowserServer(server);console.info('Teardown complete');}
});
