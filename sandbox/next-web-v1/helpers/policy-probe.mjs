import fs from 'node:fs/promises';import os from 'node:os';import net from 'node:net';
let readonly=false;try{await fs.writeFile('/opt/f01/probe','x');}catch(e){readonly=['EROFS','EACCES'].includes(e.code);}
// File permissions alone are insufficient proof of a read-only root mount.
const mounts=await fs.readFile('/proc/self/mountinfo','utf8');
readonly=readonly&&mounts.split('\n').some(line=>{const fields=line.split(' ');return fields[4]==='/'&&fields[5].split(',').includes('ro');});
const metadataBlocked=await new Promise(resolve=>{const socket=net.connect({host:'169.254.169.254',port:80});socket.setTimeout(500);socket.once('connect',()=>{socket.destroy();resolve(false);});socket.once('error',()=>resolve(true));socket.once('timeout',()=>{socket.destroy();resolve(true);});});
const status=await fs.readFile('/proc/self/status','utf8');
const read=async name=>(await fs.readFile('/sys/fs/cgroup/'+name,'utf8')).trim();
let socketAbsent=false;try{await fs.lstat('/var/run/docker.sock');}catch(e){socketAbsent=e.code==='ENOENT';}
console.log(JSON.stringify({uid:process.getuid(),gid:process.getgid(),capabilities:status.match(/CapEff:\s*(\w+)/)?.[1],noNewPrivileges:status.match(/NoNewPrivs:\s*(\d+)/)?.[1],seccomp:status.match(/Seccomp:\s*(\d+)/)?.[1],readonly,metadataBlocked,socketAbsent,interfaces:Object.keys(os.networkInterfaces()),memory:await read('memory.max'),pids:await read('pids.max'),cpu:await read('cpu.max'),memoryEvents:await read('memory.events'),envNames:Object.keys(process.env).sort(),workspaceBytes:Number((await fs.statfs('/work')).blocks*(await fs.statfs('/work')).bsize)}));
