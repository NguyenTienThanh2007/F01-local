import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import {spawn} from 'node:child_process';
if(process.argv[2]!=='serve'){
 const child=spawn('/usr/local/bin/node',['/opt/f01/static-serve.mjs','serve'],{detached:true,stdio:'ignore',cwd:'/work'});child.unref();
 console.log('{}');
}else{
 http.createServer(async(req,res)=>{
  try{
   const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
   const resolved=path.resolve('/work/out','.'+pathname);
   if(resolved!=='/work/out'&&!resolved.startsWith('/work/out/')){res.writeHead(404);return res.end();}
   let file=resolved;const stat=await fs.lstat(file);if(stat.isSymbolicLink())throw Error();if(stat.isDirectory())file=path.join(file,'index.html');
   if(!(await fs.lstat(file)).isFile())throw Error();
   const content=await fs.readFile(file);res.writeHead(200,{'Content-Type':file.endsWith('.html')?'text/html':file.endsWith('.json')?'application/json':file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'application/octet-stream'});res.end(content);
  }catch{res.writeHead(404);res.end();}
 }).listen(3000,'127.0.0.1');
}
