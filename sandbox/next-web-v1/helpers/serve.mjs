import {spawn} from 'node:child_process';
import fs from 'node:fs';
const out=fs.openSync('/dev/null','w');
spawn('/usr/local/bin/node',['/opt/f01/node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3000'],{cwd:'/work',env:process.env,detached:true,stdio:['ignore',out,out]}).unref();
console.log('{}');
