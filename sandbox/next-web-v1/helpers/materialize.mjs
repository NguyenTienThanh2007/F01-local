import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const source=JSON.parse(Buffer.from(process.argv[2], 'base64').toString('utf8'));
if(source.files.length>128)throw Error('SOURCE_BOUNDS');
// Generated apps use the immutable dependency tree baked into the trusted image.
// The writable workspace receives only a symlink to that reviewed dependency tree.
const entries=await fs.readdir('/opt/f01/scaffold',{withFileTypes:true});
for(const entry of entries){
  if(entry.name==='node_modules')continue;
  await fs.cp(
    path.join('/opt/f01/scaffold',entry.name),
    path.join('/work',entry.name),
    {recursive:true,errorOnExist:true,force:false}
  );
}
await fs.symlink('/opt/f01/scaffold/node_modules','/work/node_modules','dir');
await fs.chmod('/work',0o700);
for(const name of ['tsconfig.json','next-env.d.ts'])await fs.chmod('/work/'+name,0o644);
let bytes=0;
for(const file of source.files){
  if(!/^(app|components|lib|styles|public|tests)\//.test(file.path)||file.path.split('/').some(p=>!p||p==='.'||p==='..'||p.startsWith('.'))||file.path.includes('\\'))throw Error('SOURCE_PATH');
  const content=Buffer.from(file.content,'utf8'); bytes+=content.length;
  if(content.length>65536||bytes>524288||crypto.createHash('sha256').update(content).digest('hex')!==file.sha256)throw Error('SOURCE_BOUNDS');
  const destination=path.join('/work',file.path);
  await fs.mkdir(path.dirname(destination),{recursive:true});
  await fs.writeFile(destination,content,{flag:'wx',mode:0o644});
}
console.log(JSON.stringify({exit_code:0,duration_ms:0,diagnostics:[]}));
