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
