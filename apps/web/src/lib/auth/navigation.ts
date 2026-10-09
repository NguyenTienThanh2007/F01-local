// Only known product routes may be used as a post-login destination.
export function authDestination(value:unknown):string {
 if(typeof value!=='string'||value.length>500||/[\\\x00-\x20]/.test(value))return '/projects';
 try {const url=new URL(value,'https://f01.invalid');if(url.origin!=='https://f01.invalid'||!value.startsWith('/')||value.startsWith('//')||url.hash)return '/projects';
 if(!/^\/(?:account|projects(?:\/new|\/[0-9a-f-]{36}(?:\/(?:planning|brief|brain|activity|versions|settings))?)?)$/.test(url.pathname))return '/projects';
 for(const [key,val] of url.searchParams)if(!['step','starter','version','panel','run','change'].includes(key)||! /^[A-Za-z0-9_-]{1,100}$/.test(val))return '/projects';
 if(url.searchParams.has('change')&&(url.searchParams.getAll('change').length!==1||url.searchParams.get('change')!=='1'||!url.pathname.endsWith('/planning')))return '/projects';
 return url.pathname+url.search;}catch{return '/projects';}
}
export function signInDestination(path:string){return `/sign-in?returnTo=${encodeURIComponent(authDestination(path))}`;}
