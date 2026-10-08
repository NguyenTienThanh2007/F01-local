// Next may wait indefinitely for a held browser request during graceful exit.
// Teardown owns this child only; it must not hang or disguise a test failure.
export async function stopBrowserServer(server, timeout=5000) {
 if(!server||server.exitCode!==null||server.signalCode!==null)return;
 await new Promise(resolve=>{
  const timer=setTimeout(()=>server.kill('SIGKILL'),timeout);
  server.once('exit',()=>{clearTimeout(timer);resolve();});
  server.kill('SIGTERM');
 });
}

// Chrome descendants can inherit diagnostic pipes beyond the main process exit.
// Node's close event (which Playwright awaits) then waits for those descendants.
export function releaseExitedPipes(child) {
 const release=()=>{for(const stream of child.stdio??[])stream?.destroy?.();};
 if(child.exitCode!==null||child.signalCode!==null)release();else child.once('exit',release);
}

// Keep an explicit handle to the test-owned Chrome process. Browser.close()
// can remain pending with active network interception/streaming on this host.
// Ending that process at teardown closes its connection and preserves every
// scenario assertion and failure; no user browser or product worker is touched.
export async function launchTestBrowser(options) {
 const {chromium}=await import('playwright');
 const server=await chromium.launchServer({...options,host:'127.0.0.1'});
 releaseExitedPipes(server.process());
 let browser;
 try {browser=await chromium.connect(server.wsEndpoint());}
 catch(error){await server.kill();throw error;}
 const close=browser.close.bind(browser);
 browser.close=async()=>{const pending=close();await server.kill();await pending;};
 return browser;
}
