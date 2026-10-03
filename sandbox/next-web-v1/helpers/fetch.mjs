// Fixed loopback destination. No caller headers, redirects, cookies or credentials.
const target=process.argv[2];
if(!target.startsWith('/')||target.startsWith('//')||target.includes('\\')||target.length>2048)throw Error('PATH');
const response=await fetch('http://127.0.0.1:3000'+target,{redirect:'manual',signal:AbortSignal.timeout(5000),headers:{'Accept-Encoding':'identity'}});
const reader=response.body?.getReader();let size=0,chunks=[];
while(reader){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>2097152){await reader.cancel();throw Error('BODY_BOUNDS');}chunks.push(Buffer.from(value));}
console.log(JSON.stringify({status:response.status,type:response.headers.get('content-type')??'application/octet-stream',body:Buffer.concat(chunks).toString('base64')}));
