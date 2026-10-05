import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { mkdir, readFile } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';
const webRoot=fileURLToPath(new URL('../',import.meta.url));
const root=fileURLToPath(new URL('../../../',import.meta.url));
const api=process.env.M5_API_URL, token=process.env.M5_TEST_TOKEN;
async function until(check) { for(let n=0;n<300;n++){if(await check().catch(()=>false))return;await delay(100);}throw new Error('Expected simulation state not reached'); }
async function direct(path,options={}) { const response=await fetch(`${api}/v1${path}`,{...options,headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json',...options.headers}});assert.equal(response.ok,true,`${path}: ${response.status} ${!response.ok ? await response.text() : ''}`);return response.json(); }
async function create(title='M5 fixture') { return direct('/projects',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({title,brief:'Build a CRM with property leads, notes and a sales pipeline.'})}); }
const saved=id=>direct(`/projects/${id}/workspace`);
test('M5 real PostgreSQL/API simulation journey, replay, fallback and workspace checks',{timeout:240000},async t=>{
 assert.ok(api && token && process.env.M5_TEST_DATABASE_URL?.includes('/f01_test_'),'Use scripts/test-m5.py with its disposable database.');
 const probe=createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));const base=`http://127.0.0.1:${port}`;
 const env={...process.env,APP_ENV:'test',AUTH_MODE:'development',DEV_API_TOKEN:token,API_INTERNAL_URL:api,NEXT_PUBLIC_APP_URL:base};delete env.OPENAI_API_KEY;
 const server=spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{cwd:webRoot,env,stdio:'ignore'});let browser;
 async function scenario(name,fn){let failure;await t.test(name,async()=>{try{await fn();}catch(e){failure=e;throw e;}});if(failure)throw failure;}
 try{
  await until(async()=>(await fetch(base)).ok);browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await mkdir(`${webRoot}/test-results/m5`,{recursive:true});
  let id,firstVersion,failedRun,secondVersion;
  await scenario('create → simulated success → change → failed update → replay-safe retry → success',async()=>{
   await page.goto(`${base}/projects/new`);await page.getByRole('textbox',{name:/Project title/}).fill('Harbor M5');await page.getByRole('textbox',{name:'Product brief'}).fill('Build a CRM with property leads, notes and a sales pipeline.');
   await page.getByRole('button',{name:'Create demo project'}).click();await page.waitForURL(/\/projects\/[0-9a-f-]{36}$/);id=new URL(page.url()).pathname.split('/').at(-1);
   await page.getByRole('heading',{name:'Harbor M5',exact:true}).waitFor();await until(async()=>(await saved(id)).latest_run.status==='succeeded');await page.getByRole('heading',{name:'Demo version 1',exact:true}).waitFor();
   const initial=await saved(id);firstVersion=initial.current_version.id;assert.equal(initial.current_brain.revision,2);assert.equal(initial.project.lifecycle,'live');
   await page.getByRole('button',{name:'Inspect work',exact:true}).click();await page.getByText('Event connection: live',{exact:true}).waitFor();
   for(const phase of ['Understanding','Planning','Building','Verifying','Deploying','Live / Needs attention']) assert.equal(await page.getByRole('list',{name:'Build Trace phases'}).getByText(phase,{exact:true}).count(),1);
   assert.ok(await page.getByRole('region',{name:'Build Trace'}).getByText(/Simulation: Live/).count());
   await page.getByRole('button',{name:'Requests',exact:true}).first().click();await page.getByRole('textbox',{name:'Change request'}).fill('Add a saved priority filter for high value property leads.');await page.getByRole('checkbox',{name:'Run an optional demonstration after saving'}).check();await page.getByRole('button',{name:'Record and simulate',exact:true}).click();
   await until(async()=>(await saved(id)).latest_run.request_id!==initial.latest_run.request_id);await page.getByRole('button',{name:'Build Trace',exact:true}).click();await page.getByRole('button',{name:'Pause following',exact:true}).click();
   const trace=page.getByLabel('Ordered Build Trace',{exact:true});await trace.evaluate(element=>element.scrollTop=0);const before=await trace.locator('li[data-sequence]').count();
   await until(async()=>(await saved(id)).latest_run.status==='failed');await page.getByText(/Latest update needs attention/).waitFor();assert.equal(await trace.evaluate(element=>element.scrollTop),0);assert.ok(await trace.locator('li[data-sequence]').count()>before);await page.getByRole('button',{name:/Jump to latest/}).click();
   await until(async()=>await trace.evaluate(element=>element.scrollHeight-element.clientHeight-element.scrollTop<24));
   const latestBox=await trace.locator('li[data-sequence]').last().boundingBox();assert.ok(latestBox && latestBox.y+latestBox.height<=1000,'Latest followed event stays inside viewport');
   const failed=await saved(id);failedRun=failed.latest_run.id;assert.equal(failed.current_version.id,firstVersion);assert.equal(failed.current_brain.id,initial.current_brain.id);assert.equal(await page.locator('iframe').getAttribute('sandbox'),'allow-scripts');
   await page.getByRole('button',{name:'Run details',exact:true}).click();await page.getByRole('heading',{name:'Attempt 1 · failed',exact:true}).waitFor();
   const commands=[];
   await page.route('**/api/v1/projects/*/runs/*/retry',async route=>{commands.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();assert.equal(response.status(),202);await route.abort('failed');});
   await page.getByRole('button',{name:'Retry simulation',exact:true}).click();await page.getByRole('button',{name:'Resolve saved simulation command',exact:true}).waitFor();await page.unroute('**/api/v1/projects/*/runs/*/retry');
   await page.reload();await page.getByRole('button',{name:'Resolve saved simulation command',exact:true}).waitFor();page.on('request',request=>{if(request.method()==='POST'&&request.url().endsWith(`/runs/${failedRun}/retry`))commands.push({key:request.headers()['idempotency-key'],body:request.postDataJSON()});});
   await page.getByRole('button',{name:'Resolve saved simulation command',exact:true}).click();await until(async()=>(await saved(id)).latest_run.status==='succeeded'&&(await saved(id)).current_version.number===2);await page.getByRole('heading',{name:'Demo version 2',exact:true}).waitFor();
   assert.equal(commands.length,2);assert.equal(commands[0].key,commands[1].key);assert.deepEqual(commands[0].body,commands[1].body);
   const success=await saved(id);secondVersion=success.current_version.id;assert.equal(success.latest_run.retry_of_run_id,failedRun);assert.equal(success.latest_run.attempt,2);assert.equal(success.current_brain.revision,3);assert.equal((await direct(`/projects/${id}/runs/${failedRun}`)).status,'failed');
   const requests=(await direct(`/projects/${id}/requests`)).items;assert.equal(requests.length,2);assert.equal(requests.find(r=>r.kind==='initial').text,'Build a CRM with property leads, notes and a sales pipeline.');assert.equal(requests.find(r=>r.kind==='change').base_version_id,firstVersion);
   const deployments=(await direct(`/projects/${id}/deployments`)).items;assert.equal(deployments.length,2);assert.ok(deployments.every(d=>d.mode==='simulated'&&d.external_url===null&&d.target==='internal_fixture'));
   const second=await browser.newPage();await second.goto(`${base}/projects/${id}`);await second.getByRole('heading',{name:'Demo version 2',exact:true}).waitFor();await second.close();await page.reload();await page.getByRole('heading',{name:'Demo version 2',exact:true}).waitFor();
  });
  await scenario('historical version, Brain and run inspection preserve current pointers',async()=>{
   await page.goto(`${base}/projects/${id}/versions`);await page.getByRole('link',{name:/Inspect demo preview/}).last().click();await page.getByRole('heading',{name:'Demo version 1',exact:true}).waitFor();await page.getByText(/Historical demo version · inspection only/).waitFor();assert.equal((await saved(id)).current_version.id,secondVersion);
   await page.goto(`${base}/projects/${id}/brain?revision=1`);await page.getByText('Immutable revision 1',{exact:true}).waitFor();assert.equal((await saved(id)).current_brain.revision,3);
   await page.goto(`${base}/projects/${id}?panel=run&run=${failedRun}`);await page.getByRole('heading',{name:'Attempt 1 · failed',exact:true}).waitFor();assert.equal((await saved(id)).current_version.id,secondVersion);
  });
  await scenario('recoverable fixture issue and repair remain linked in the Trace and Brain',async()=>{
   const current=await saved(id);const request=await direct(`/projects/${id}/requests`,{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({text:'Explore a recoverable sample callback verification scenario.',base_brain_revision_id:current.current_brain.id,base_version_id:current.current_version.id})});
   const configured=spawnSync(`${root}/apps/api/.venv/bin/python`,['-m','tests.browser_fixture',process.env.M5_TEST_DATABASE_URL,'recoverable-run'],{cwd:`${root}/apps/api`,input:JSON.stringify({project:{id},request_id:request.id}),encoding:'utf8'});assert.equal(configured.status,0,configured.stderr);const run=JSON.parse(configured.stdout);
   await page.goto(`${base}/projects/${id}?panel=trace`);await until(async()=>(await saved(id)).latest_run.status==='succeeded');await page.getByText(`Issue: ${run.id}:sample-auth-callback`,{exact:true}).waitFor();await page.getByText(/Linked fixture repair at sequence/).waitFor();await page.getByText(`Fixture repair → issue ${run.id}:sample-auth-callback`,{exact:true}).waitFor();
   const repairLink=page.getByRole('link',{name:/Linked fixture repair at sequence/});const repairTarget=(await repairLink.getAttribute('href')).slice(1);await repairLink.click();assert.equal(await page.evaluate(()=>document.activeElement.id),repairTarget);await page.getByRole('button',{name:/Jump to latest/}).click();const issueLink=page.getByRole('link',{name:`Fixture repair → issue ${run.id}:sample-auth-callback`,exact:true});const issueTarget=(await issueLink.getAttribute('href')).slice(1);await issueLink.click();assert.equal(await page.evaluate(()=>document.activeElement.id),issueTarget);await page.getByRole('button',{name:/Jump to latest/}).click();const brain=await direct(`/projects/${id}/brain`);assert.ok(brain.revision.content.history.issue_ids.includes(`${run.id}:sample-auth-callback`));secondVersion=(await saved(id)).current_version.id;await page.screenshot({path:`${webRoot}/test-results/m5/repair-1440.png`,fullPage:true});
  });
  await scenario('sequence gap and duplicate SSE delivery recover before later events apply',async()=>{
   const created=await create('Gap recovery');const pid=created.project.id;const gapPage=await browser.newPage();let deliveries=0;
   await gapPage.route('**/api/v1/projects/*/events/stream?**',async route=>{
    const cursor=Number(new URL(route.request().url()).searchParams.get('after_sequence'));await until(async()=>(await saved(pid)).latest_run.status==='succeeded');
    const events=(await direct(`/projects/${pid}/events?after_sequence=${cursor}&limit=100`)).items;
    if(!events.length)return route.fulfill({status:200,contentType:'text/event-stream',body:': heartbeat\n\n'});
    deliveries++;const last=events.at(-1);const wire=[last,...events,last].map(event=>`event: build_event\nid: ${event.sequence}\ndata: ${JSON.stringify(event)}\n\n`).join('');await route.fulfill({status:200,contentType:'text/event-stream',body:wire});
   });
   await gapPage.goto(`${base}/projects/${pid}?panel=trace`);await gapPage.getByRole('heading',{name:'Demo version 1',exact:true}).waitFor();await until(async()=>deliveries>0);
   const expected=(await direct(`/projects/${pid}/events?limit=100`)).items.map(e=>e.sequence);
   await until(async()=>await gapPage.locator('.trace-scroll li[data-sequence]').count()===expected.length);
   assert.deepEqual(await gapPage.locator('.trace-scroll li[data-sequence]').evaluateAll(items=>items.map(item=>Number(item.dataset.sequence))),expected);await gapPage.close();
  });
  await scenario('polling fallback progresses when EventSource is unavailable',async()=>{
   const created=await create('Polling recovery');const pid=created.project.id;const pollingPage=await browser.newPage();await pollingPage.addInitScript(()=>{window.EventSource=undefined;});let polls=0;pollingPage.on('request',request=>{if(request.url().includes('/events?after_sequence='))polls++;});
   await pollingPage.goto(`${base}/projects/${pid}?panel=trace`);await pollingPage.getByText('Event connection: polling',{exact:true}).waitFor();await pollingPage.getByRole('heading',{name:'Demo version 1',exact:true}).waitFor();assert.ok(polls>=2);assert.equal((await saved(pid)).project.lifecycle,'live');await pollingPage.close();
  });
  await scenario('terminated streams poll and reconnect with a recovered sequence cursor',async()=>{
   const created=await create('Reconnect recovery');const pid=created.project.id;const reconnectPage=await browser.newPage();const cursors=[];let attempts=0;
   await reconnectPage.route('**/api/v1/projects/*/events/stream?**',async route=>{cursors.push(Number(new URL(route.request().url()).searchParams.get('after_sequence')));attempts++;if(attempts<=2)return route.abort('failed');return route.continue();});
   await reconnectPage.goto(`${base}/projects/${pid}?panel=trace`);await reconnectPage.getByText('Event connection: polling',{exact:true}).waitFor();await reconnectPage.getByText('Event connection: live',{exact:true}).waitFor();await reconnectPage.getByRole('heading',{name:'Demo version 1',exact:true}).waitFor();
   assert.ok(cursors.length>=3);assert.ok(cursors.at(-1)>cursors[0]);const sequences=await reconnectPage.locator('.trace-scroll li[data-sequence]').evaluateAll(items=>items.map(item=>Number(item.dataset.sequence)));assert.equal(new Set(sequences).size,sequences.length);await reconnectPage.close();
  });
  await scenario('active cancellation and stale draft review retain immutable original input',async()=>{
   const created=await create('Cancel fixture');const pid=created.project.id;await page.goto(`${base}/projects/${pid}?panel=run`);await page.getByRole('button',{name:'Cancel simulation',exact:true}).click();await until(async()=>(await saved(pid)).latest_run.status==='canceled');assert.equal((await saved(pid)).project.lifecycle,'idle');assert.equal((await saved(pid)).current_version,null);
   await direct(`/projects/${pid}/runs/${created.run_id}/cancel`,{method:'POST',body:'{}'});await page.getByRole('heading',{name:'Preview pending.',exact:true}).waitFor();
   const stale=await create('Stale draft fixture');const sid=stale.project.id;await page.goto(`${base}/projects/${sid}?panel=requests`);const draft=page.getByRole('textbox',{name:'Change request'});await draft.fill('Keep this draft while the initial simulation changes its base context.');
   await until(async()=>(await saved(sid)).latest_run.status==='succeeded');await page.getByRole('button',{name:'Review current context',exact:true}).waitFor();assert.equal(await draft.inputValue(),'Keep this draft while the initial simulation changes its base context.');await page.getByRole('button',{name:'Review current context',exact:true}).click();await until(async()=>!(await page.getByRole('button',{name:'Record change request',exact:true}).isDisabled()));assert.equal(await draft.inputValue(),'Keep this draft while the initial simulation changes its base context.');
   await page.getByRole('button',{name:'Close inspector'}).click();
  });
  await scenario('responsive Trace, run details and preview isolation at four widths',async()=>{
   for(const width of [375,768,1280,1440]){
    await page.setViewportSize({width,height:1000});await page.goto(`${base}/projects/${id}?panel=trace`);await page.getByRole('heading',{name:'Saved execution timeline',exact:true}).waitFor();await page.evaluate(()=>document.fonts.ready);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}px overflow`);
    if(process.env.M5_AXE_SCRIPT){await page.addScriptTag({content:await readFile(process.env.M5_AXE_SCRIPT,'utf8')});assert.deepEqual(await page.evaluate(async()=>(await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))),[],`${width}px accessibility`);}
    await page.screenshot({path:`${webRoot}/test-results/m5/trace-${width}.png`,fullPage:true});await page.getByRole('button',{name:'Run details',exact:true}).click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.getByRole('button',{name:'Close inspector'}).click();assert.equal(await page.locator('iframe').getAttribute('sandbox'),'allow-scripts');
   }
   const child=page.frames().find(frame=>frame.url().includes('/demo-preview/crm-v1'));assert.ok(child);
   const blocked=await child.evaluate(async()=>{const result={};for(const [name,fn] of [['parent',()=>parent.document],['storage',()=>localStorage.getItem('x')],['cookies',()=>document.cookie]]){try{fn();result[name]=false;}catch{result[name]=true;}}try{await fetch('/api/v1/projects');result.fetch=false;}catch{result.fetch=true;}return result;});assert.deepEqual(blocked,{parent:true,storage:true,cookies:true,fetch:true});assert.deepEqual(errors,[]);
  });
 }finally{await browser?.close();server.kill('SIGTERM');}
});
