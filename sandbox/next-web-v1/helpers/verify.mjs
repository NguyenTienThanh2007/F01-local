import fs from 'node:fs/promises';import crypto from 'node:crypto';
const source=JSON.parse(Buffer.from(process.argv[2],'base64').toString('utf8'));
let valid=true;
for(const file of source.files){const stat=await fs.lstat('/work/'+file.path);if(!stat.isFile()||stat.isSymbolicLink()||crypto.createHash('sha256').update(await fs.readFile('/work/'+file.path)).digest('hex')!==file.sha256)valid=false;}
for(const name of ['package.json','pnpm-lock.yaml','.npmrc','next.config.mjs'])if(!Buffer.from(await fs.readFile('/work/'+name)).equals(await fs.readFile('/opt/f01/scaffold/'+name)))valid=false;
console.log(JSON.stringify({exit_code:valid?0:1,duration_ms:0,diagnostics:valid?[]:[{code:'SOURCE_MUTATED'}]}));
