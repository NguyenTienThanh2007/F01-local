import fs from 'node:fs/promises';

const link='/work/node_modules';
const trusted='/opt/f01/scaffold/node_modules';

let valid=true;

try {
  const stat=await fs.lstat(link);
  if(!stat.isSymbolicLink())valid=false;

  const resolved=await fs.realpath(link);
  if(resolved!==trusted)valid=false;

  const trustedStat=await fs.stat(trusted);
  if(!trustedStat.isDirectory())valid=false;

  for(const name of [
    'next/package.json',
    'react/package.json',
    'react-dom/package.json',
    'typescript/package.json'
  ]){
    const stat=await fs.stat(`${trusted}/${name}`);
    if(!stat.isFile())valid=false;
  }

  for(const name of [
    'package.json',
    'pnpm-lock.yaml',
    '.npmrc',
    'next.config.mjs'
  ]){
    const working=await fs.readFile(`/work/${name}`);
    const immutable=await fs.readFile(`/opt/f01/scaffold/${name}`);
    if(!working.equals(immutable))valid=false;
  }
} catch {
  valid=false;
}

process.exit(valid?0:1);
