// Real generated TaskPilot acceptance: no model, source, API or page route mocks.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import path from 'node:path';
import {createRequire} from 'node:module';
import {auditGeneratedPage,auditGeneratedEditor} from '../../../apps/web/tests/generated-visual-acceptance.mjs';
const require=createRequire(new URL('../../../apps/web/package.json',import.meta.url)),{chromium,expect}=require('playwright/test');
const state=JSON.parse(await fs.readFile(path.resolve(process.env.F01_TASKPILOT_STATE_PATH || '.runtime/taskpilot/state.json'),'utf8'));
const version=state.versions.at(-1),url=version.descriptor.browser_url;
assert.ok(version.number>=6,'A new real generated version is required');
const baseline=JSON.parse(await fs.readFile(new URL('../reports/saved-v3-acceptance-tasks.json',import.meta.url),'utf8'));
const directory=path.resolve(process.env.F01_TASKPILOT_ACCEPTANCE_OUTPUT || '.runtime/taskpilot-quality/recheck')+'/';await fs.mkdir(directory,{recursive:true});
const report={version:version.number,sourceDigest:version.descriptor.source_digest,checks:[],consoleErrors:[],pageErrors:[],data:'Main persistent profile retains actual v3 records; isolated recovery/date contexts use labelled disposable task data, not mock applications.'};
let context;
const record=async(name,fn)=>{try{const evidence=await fn();report.checks.push({name,passed:true,evidence:evidence??null});console.log('PASS',name);}catch(e){report.checks.push({name,passed:false,error:String(e.message).replaceAll(url,'[private local preview]')});console.log('FAIL',name,String(e.message).replaceAll(url,'[private local preview]'));}await fs.writeFile(directory+'functional.json',JSON.stringify(report,null,2));};
const tasks=p=>p.evaluate(()=>JSON.parse(localStorage.getItem('taskpilot_tasks_v1')||'[]'));
const card=(p,title)=>p.locator('li').filter({has:p.getByRole('heading',{name:title,exact:true})});
const newButton=p=>p.getByRole('button',{name:'New Task',exact:true});
const dialog=p=>p.getByRole('dialog');
const visibleTask=(p,title)=>expect(card(p,title)).toBeVisible();
const title='QA acceptance — compact board';const edited=title+' edited';const mobileTitle='QA mobile — compact editor';
try{
 context=await chromium.launchPersistentContext(path.resolve(process.env.F01_TASKPILOT_PROFILE_DIR || '.runtime/taskpilot/browser-profile'),{headless:true,viewport:{width:1440,height:900}});
 await context.addInitScript(()=>{window.__storageWrites=[];const original=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='taskpilot_tasks_v1')window.__storageWrites.push(v);return original.call(this,k,v)}});
 const page=context.pages()[0];page.setDefaultTimeout(8000);page.on('pageerror',e=>report.pageErrors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text())});
 await page.goto(url,{waitUntil:'networkidle'});
 await record(`v3 saved records and IDs survive v${version.number} without initial empty write`,async()=>{
  const loaded=await tasks(page);assert.deepEqual(loaded,baseline);const writes=await page.evaluate(()=>window.__storageWrites.map(v=>JSON.parse(v)));assert.ok(writes.length>0);assert.ok(writes.every(v=>v.length>=baseline.length));return {existingRecords:loaded.length,firstWriteCount:writes[0].length};
 });
 await record('New Task opens; initial focus, Tab trap, Escape and Cancel restore invoking control',async()=>{
  await newButton(page).click();await expect(dialog(page)).toBeVisible();await expect(dialog(page).getByLabel('Title')).toBeFocused();
  for(let i=0;i<14;i++){await page.keyboard.press('Tab');assert.equal(await dialog(page).evaluate(el=>el.contains(document.activeElement)),true)}
  for(let i=0;i<14;i++){await page.keyboard.press('Shift+Tab');assert.equal(await dialog(page).evaluate(el=>el.contains(document.activeElement)),true)}
  await page.keyboard.press('Escape');await expect(dialog(page)).toBeHidden();await expect(newButton(page)).toBeFocused();
  await newButton(page).click();await dialog(page).getByRole('button',{name:'Cancel',exact:true}).click();await expect(newButton(page)).toBeFocused();
 });
 await record('Required validation prevents blank task; create task with priority and overdue date',async()=>{
  await newButton(page).click();await dialog(page).getByRole('button',{name:'Add Task',exact:true}).click();await expect(page.getByText('Title is required',{exact:true})).toBeVisible();assert.equal((await tasks(page)).length,baseline.length);
  await dialog(page).getByLabel('Title').fill(title);await dialog(page).getByLabel('Description',{exact:true}).fill('Real browser acceptance; delete only this disposable task.');await dialog(page).getByLabel('Priority',{exact:true}).selectOption('High');await dialog(page).getByLabel('Due Date',{exact:true}).fill('2026-10-09');await dialog(page).getByRole('button',{name:'Add Task',exact:true}).click();await visibleTask(page,title);await expect(card(page,title)).toContainText('High');await expect(card(page,title)).toContainText('Overdue');
 });
 await record('Edit preserves ID, changes priority/due date, restores Edit invoker',async()=>{
  const id=(await tasks(page)).find(t=>t.title===title).id;const invoking=card(page,title).getByRole('button',{name:'Edit Task',exact:true});await invoking.click();await page.keyboard.press('Escape');await expect(invoking).toBeFocused();await invoking.click();await dialog(page).getByRole('button',{name:'Cancel',exact:true}).click();await expect(invoking).toBeFocused();
  await invoking.click();await dialog(page).getByLabel('Title').fill(edited);await dialog(page).getByLabel('Priority',{exact:true}).selectOption('Low');await dialog(page).getByLabel('Due Date',{exact:true}).fill('2026-10-17');await dialog(page).getByRole('button',{name:'Update Task',exact:true}).click();await visibleTask(page,edited);await expect(card(page,edited).getByRole('button',{name:'Edit Task',exact:true})).toBeFocused();assert.equal((await tasks(page)).find(t=>t.title===edited).id,id);await expect(card(page,edited)).toContainText('Low');assert.ok(!(await card(page,edited).innerText()).includes('Overdue'));
 });
 await record('Move task Todo → In Progress → Done and back with real persisted status',async()=>{
  for(const expected of ['In Progress','Done']) {await card(page,edited).getByRole('button',{name:'Move Right',exact:true}).click();assert.equal((await tasks(page)).find(t=>t.title===edited).status,expected)}
  await expect(card(page,edited).getByRole('button',{name:'Move Right',exact:true})).toBeDisabled();await card(page,edited).getByRole('button',{name:'Move Left',exact:true}).click();assert.equal((await tasks(page)).find(t=>t.title===edited).status,'In Progress');
 });
 await record('Search/status/priority filtering and no-results Reset work',async()=>{
  await page.getByRole('searchbox',{name:'Search tasks'}).fill(edited);await expect(page.locator('li')).toHaveCount(1);await page.getByLabel('Filter by status',{exact:true}).selectOption('Todo');await expect(page.locator('li')).toHaveCount(0);await expect(page.getByRole('button',{name:'Reset filters',exact:true}).first()).toBeVisible();await page.getByRole('button',{name:'Reset filters',exact:true}).first().click();await expect(page.locator('li')).toHaveCount(baseline.length+1);
  await page.getByLabel('Filter by priority',{exact:true}).selectOption('Low');await expect(page.locator('li')).toHaveCount(1);await visibleTask(page,edited);await page.getByLabel('Filter by priority',{exact:true}).selectOption('All');
 });
 await record('Refresh keeps exact tasks and does not write empty initial state',async()=>{const before=await tasks(page);await page.reload({waitUntil:'networkidle'});assert.deepEqual(await tasks(page),before);const writes=await page.evaluate(()=>window.__storageWrites.map(v=>JSON.parse(v).length));assert.ok(writes.every(n=>n>=baseline.length));return {recordCount:before.length,initialWrites:writes};});
 await record('Delete confirmation can cancel; confirmed delete removes only the disposable task',async()=>{
  await card(page,edited).getByRole('button',{name:'Delete Task',exact:true}).click();await card(page,edited).getByRole('button',{name:'Cancel Delete Task',exact:true}).click();await visibleTask(page,edited);await card(page,edited).getByRole('button',{name:'Delete Task',exact:true}).click();await card(page,edited).getByRole('button',{name:'Confirm Delete Task',exact:true}).click();await expect(card(page,edited)).toHaveCount(0);assert.deepEqual(await tasks(page),baseline);
 });
 await record('Mobile create/edit/reload/delete with preserved original records',async()=>{
  await page.setViewportSize({width:390,height:844});await newButton(page).click();await dialog(page).getByLabel('Title').fill(mobileTitle);await dialog(page).getByLabel('Priority',{exact:true}).selectOption('Medium');await dialog(page).getByLabel('Due Date',{exact:true}).fill('2026-10-10');await dialog(page).getByRole('button',{name:'Add Task',exact:true}).click();await card(page,mobileTitle).getByRole('button',{name:'Edit Task',exact:true}).click();await dialog(page).getByLabel('Description',{exact:true}).fill('Edited on the actual mobile layout');await dialog(page).getByRole('button',{name:'Update Task',exact:true}).click();await page.reload({waitUntil:'networkidle'});await expect(card(page,mobileTitle)).toContainText('Edited on the actual mobile layout');await card(page,mobileTitle).getByRole('button',{name:'Delete Task',exact:true}).click();await card(page,mobileTitle).getByRole('button',{name:'Confirm Delete Task',exact:true}).click();assert.deepEqual(await tasks(page),baseline);
 });
 await record('Actual board visual measurements and axe at four responsive widths',async()=>{report.board=await auditGeneratedPage(page,{directory:directory+'board',primarySelector:'.kanban'});assert.equal(report.board.deterministicPassed,true);assert.equal(report.board.accessibilityPassed,true);return report.board.states.map(s=>({name:s.name,boardTop:s.metrics.primary.top,overflow:s.metrics.pageWidth-s.metrics.viewport.width,controls:s.metrics.controls.map(c=>c.height),violations:s.accessibility.violations.length}));});
 await record('Actual New Task editor opens and passes compact sizing/axe desktop and mobile',async()=>{report.editor=await auditGeneratedEditor(page,{directory:directory+'editor',actionName:'New Task'});assert.equal(report.editor.opened,true);assert.equal(report.editor.deterministicPassed,true);assert.equal(report.editor.accessibilityPassed,true);});
 const browser=await chromium.launch({headless:true});
 try{
  await record('Malformed storage is preserved with a truthful warning and no writes',async()=>{
   const c=await browser.newContext();const p=await c.newPage();try{await p.goto(url,{waitUntil:'networkidle'});await p.evaluate(()=>localStorage.setItem('taskpilot_tasks_v1','[{broken'));await p.reload({waitUntil:'networkidle'});await expect(p.getByText(/Stored task data is corrupted/)).toBeVisible();assert.equal(await p.evaluate(()=>localStorage.getItem('taskpilot_tasks_v1')),'[{broken');await expect(newButton(p)).toBeDisabled();await p.screenshot({path:directory+'corrupt-storage.png'});}finally{await c.close()}
  });
  await record('Local calendar-day overdue boundaries and unknown-field compatibility',async()=>{
   const c=await browser.newContext({timezoneId:'Pacific/Honolulu'});const p=await c.newPage();try{await p.clock.install({time:new Date('2026-10-10T03:30:00Z')});await p.goto(url,{waitUntil:'networkidle'});await p.evaluate(()=>localStorage.setItem('taskpilot_tasks_v1',JSON.stringify([{id:'date-today',title:'Local today',description:'',status:'Todo',priority:'Medium',dueDate:'2026-10-09',retainedExtension:{flag:true}},{id:'date-yesterday',title:'Local yesterday',description:'',status:'Todo',priority:'High',dueDate:'2026-10-08'},{id:'date-done',title:'Past but done',description:'',status:'Done',priority:'Low',dueDate:'2026-10-08'}])));await p.reload({waitUntil:'networkidle'});assert.ok(!(await card(p,'Local today').innerText()).includes('Overdue'));await expect(card(p,'Local yesterday')).toContainText('Overdue');assert.ok(!(await card(p,'Past but done').innerText()).includes('Overdue'));await card(p,'Local today').getByRole('button',{name:'Edit Task',exact:true}).click();await dialog(p).getByLabel('Description',{exact:true}).fill('Compatible unknown field');await dialog(p).getByRole('button',{name:'Update Task',exact:true}).click();assert.deepEqual((await tasks(p)).find(t=>t.id==='date-today').retainedExtension,{flag:true});}finally{await c.close()}
  });
  await record('Empty and no-results actual views remain usable',async()=>{
   const c=await browser.newContext({viewport:{width:1440,height:900}});const p=await c.newPage();try{await p.goto(url,{waitUntil:'networkidle'});await expect(p.locator('li')).toHaveCount(0);await p.screenshot({path:directory+'empty.png'});await newButton(p).click();await dialog(p).getByLabel('Title').fill('Disposable empty-state check');await dialog(p).getByRole('button',{name:'Add Task',exact:true}).click();await p.getByRole('searchbox',{name:'Search tasks'}).fill('no matching title');await expect(p.getByRole('button',{name:'Reset filters',exact:true}).first()).toBeVisible();await p.screenshot({path:directory+'no-results.png'});}finally{await c.close()}
  });
 }finally{await browser.close()}
 await record('No critical console errors or uncaught page exceptions',async()=>{assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);});
}finally{await context?.close();report.passed=report.checks.every(c=>c.passed);await fs.writeFile(directory+'functional.json',JSON.stringify(report,null,2));console.log(JSON.stringify({version:report.version,passed:report.passed,checks:report.checks.length,failed:report.checks.filter(c=>!c.passed).map(c=>c.name)}));if(!report.passed)process.exitCode=1;}
