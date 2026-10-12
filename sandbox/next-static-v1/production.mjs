// Application-owned production packaging. Executed only in the trusted sandbox.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
const source=JSON.parse(Buffer.from(process.argv[2],'base64').toString('utf8'));
const marker=JSON.parse(Buffer.from(process.argv[3],'base64').toString('utf8'));
const configuration="export default {output:'export',trailingSlash:true,experimental:{cpus:1},poweredByHeader:false,productionBrowserSourceMaps:false,images:{unoptimized:true}};\n";
const evidence=[];let stage='configuration';
async function command(phase,argv){
 stage=phase;
 const started=Date.now();
 const result=await new Promise((resolve,reject)=>{
  const child=spawn('/usr/local/bin/node',['/opt/f01/command.mjs',phase,...argv],{cwd:'/work',stdio:['ignore','pipe','ignore']});
  let output='';child.stdout.on('data',chunk=>{output+=chunk;if(output.length>8192){child.kill('SIGKILL');reject(Error('OUTPUT_LIMIT'));}});
  const timer=setTimeout(()=>{child.kill('SIGKILL');reject(Error('COMMAND_TIMEOUT'));},phase==='build'?130000:70000);
  child.on('error',reject);child.on('close',code=>{clearTimeout(timer);if(code!==0)return reject(Error('COMMAND_FAILED'));try{resolve(JSON.parse(output));}catch{reject(Error('EVIDENCE_INVALID'));}});
 });
 evidence.push({...result,phase,argv:argv.slice(0,2),duration_ms:Math.min(Date.now()-started,1200000)});
 if(result.exit_code!==0)throw Error('PRODUCTION_VERIFICATION_FAILED');
}
try{
 if(source.files.some(f=>f.path==='public/__f01_release.json'))throw Error('RESERVED_MARKER');
 await command('install',['/usr/local/bin/node','/opt/f01/dependency-check.mjs']);
 stage='configuration';
 await fs.chmod('/work/next.config.mjs',0o644);
 await fs.writeFile('/work/next.config.mjs',configuration,{mode:0o644});
 // Only the application-owned production configuration differs from the preview scaffold.
 await command('typecheck',['/usr/local/bin/node','/opt/f01/node_modules/typescript/bin/tsc','--noEmit']);
 await command('build',['/usr/local/bin/node','/opt/f01/node_modules/next/dist/bin/next','build','--webpack']);
 const tests=source.files.filter(f=>f.path.startsWith('tests/')&&f.path.endsWith('.test.mjs')).map(f=>f.path).sort();
 if(!tests.length||tests.length>16)throw Error('TEST_POLICY');
 await command('test',['/usr/local/bin/node','--test','--',...tests]);
 stage='integrity';
 for(const file of source.files){const stat=await fs.lstat('/work/'+file.path);if(!stat.isFile()||stat.isSymbolicLink()||crypto.createHash('sha256').update(await fs.readFile('/work/'+file.path)).digest('hex')!==file.sha256)throw Error('SOURCE_MUTATED');}
 if((await fs.readFile('/work/next.config.mjs','utf8'))!==configuration)throw Error('CONFIG_MUTATED');
 for(const name of ['package.json','pnpm-lock.yaml','.npmrc'])if(!Buffer.from(await fs.readFile('/work/'+name)).equals(await fs.readFile('/opt/f01/scaffold/'+name)))throw Error('SCAFFOLD_MUTATED');
 stage='export';
 const files=[];let bytes=0;
 async function add(path,data){bytes+=data.length;if(bytes>16777216||files.length>=2000)throw Error('PACKAGE_BOUNDS');files.push({path,data:data.toString('base64'),sha256:crypto.createHash('sha256').update(data).digest('hex')});}
 async function walk(relative=''){
  for(const name of await fs.readdir('/work/out/'+relative)){
   const path=relative+name;const stat=await fs.lstat('/work/out/'+path);
   if(stat.isSymbolicLink())throw Error('PACKAGE_LINK');
   if(stat.isDirectory())await walk(path+'/');
   else if(stat.isFile()){
    if(stat.size>16777216)throw Error('PACKAGE_BOUNDS');
    const data=await fs.readFile('/work/out/'+path);if(data.includes(Buffer.from('/p/')))throw Error('PREVIEW_PATH_IN_OUTPUT');
    await add('.vercel/output/static/'+path,data);
   }else throw Error('PACKAGE_TYPE');
  }
 }
 await walk();
 await add('.vercel/output/config.json',Buffer.from(JSON.stringify({version:3,routes:[{handle:'filesystem'}]})));
 const markerData=Buffer.from(JSON.stringify(marker));
 await fs.writeFile('/work/out/__f01_release.json',markerData,{flag:'wx',mode:0o644});
 await add('.vercel/output/static/__f01_release.json',markerData);
 const lock_digest=crypto.createHash('sha256').update(await fs.readFile('/opt/f01/scaffold/pnpm-lock.yaml')).digest('hex');
 console.log(JSON.stringify({package:{files},evidence,lock_digest,configuration_digest:crypto.createHash('sha256').update(configuration).digest('hex'),platform:process.platform,architecture:process.arch}));
}catch{console.log(JSON.stringify({error:'PRODUCTION_'+stage.toUpperCase()+'_FAILED',evidence}));}
