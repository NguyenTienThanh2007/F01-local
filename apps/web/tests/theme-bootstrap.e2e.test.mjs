import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {writeFile} from 'node:fs/promises';
import {setTimeout as delay} from 'node:timers/promises';
import {launchTestBrowser,stopBrowserServer} from './browser-process.mjs';
import {verifyThemeBootstrap} from './theme-bootstrap-acceptance.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
test('theme and native preference control are correct before React hydration',{timeout:60000},async()=>{
 const probe=createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
 const base=`http://127.0.0.1:${port}`,directory=root+'/test-results/editorial-bootstrap';
 const env={...process.env,APP_ENV:'test',AUTH_MODE:'development',EXECUTION_MODE:'simulated',DEV_API_TOKEN:'synthetic-theme-browser-token-12345678901234567890',API_INTERNAL_URL:'http://127.0.0.1:9',NEXT_PUBLIC_APP_URL:base};delete env.OPENAI_API_KEY;delete env.F01_VERCEL_TOKEN;
 const server=spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{cwd:root,env,stdio:'ignore'});let browser;
 try{
  let ready=false;for(let attempt=0;attempt<100;attempt++){if(await fetch(base).then(r=>r.ok).catch(()=>false)){ready=true;break;}await delay(100);}assert.ok(ready,'Owned test frontend must become ready.');
  browser=await launchTestBrowser({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
  const no_flash=await verifyThemeBootstrap(browser,base,directory);await writeFile(directory+'/result.json',JSON.stringify({status:'passed',no_flash},null,2));
 }finally{await browser?.close();await stopBrowserServer(server);}
});
