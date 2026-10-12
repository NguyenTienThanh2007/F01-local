// Opt-in acceptance probe: fresh browser context, no factory identity or credentials.
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const [origin,markerJSON,mode]=process.argv.slice(2);
assert.match(origin,/^https:\/\/[a-z0-9][a-z0-9-]{0,100}\.vercel\.app$/);
const marker=JSON.parse(markerJSON);
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
try{
 const context=await browser.newContext(),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin,{waitUntil:'networkidle',timeout:30000});
 await page.getByRole('main').filter({hasText:'Verified dashboard'}).waitFor();
 const observed=await page.evaluate(async()=>{const response=await fetch('/__f01_release.json',{cache:'no-store'});return response.json();});
 assert.deepEqual(observed,marker);
 if(mode==='priority'){
  await page.getByLabel('Priority filter').selectOption('high');
  await page.getByText('Orchard',{exact:true}).waitFor({state:'hidden'});
  await page.getByText('Harbor',{exact:true}).waitFor();
 }
 assert.deepEqual(errors,[]);
 assert.deepEqual(await context.cookies(),[]);
 console.log(JSON.stringify({public_browser:'passed',mode,origin,identity:'no factory cookies or tokens'}));
}finally{await browser.close();}
