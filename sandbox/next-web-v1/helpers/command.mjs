import {spawn} from 'node:child_process';
const [phase,...argv]=process.argv.slice(2);
const start=Date.now(); let sample='',bytes=0;
const child=spawn(argv[0],argv.slice(1),{cwd:'/work',env:process.env,stdio:['ignore','pipe','pipe']});
function collect(chunk){bytes+=chunk.length;if(sample.length<32768)sample+=chunk.toString().slice(0,32768-sample.length);if(bytes>1048576)child.kill('SIGKILL');}
child.stdout.on('data',collect);child.stderr.on('data',collect);
child.on('error',()=>{console.log(JSON.stringify({exit_code:127,duration_ms:Date.now()-start,diagnostics:[{code:'COMMAND_UNAVAILABLE'}]}));process.exit(0);});
child.on('close',code=>{
 const diagnostics=[];
 for(const match of sample.matchAll(/((?:app|components|lib|styles)\/[A-Za-z0-9_./\[\]()-]+)\((\d+),\d+\): error (TS\d+):/g)){
  if(diagnostics.length<16)diagnostics.push({code:match[3],path:match[1],line:Number(match[2])});
 }
 if(code!==0&&!diagnostics.length)diagnostics.push({code:bytes>1048576?'OUTPUT_LIMIT':phase.toUpperCase()+'_FAILED'});
 console.log(JSON.stringify({exit_code:code??137,duration_ms:Date.now()-start,diagnostics}));
});
