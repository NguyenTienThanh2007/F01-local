// Minimal hand-written HARNESS fixtures for generated-app-acceptance regressions.
// They are not generated applications and never count as model or Docker acceptance.
const page = (title, body, script) => `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title>
<style>*,*::before,*::after{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,sans-serif;color:#1a1a1a;background:#fff}
main{max-width:960px;margin:0 auto;padding:16px}input,select,textarea,button{font:inherit;font-size:16px;min-height:44px;padding:6px 10px}
ul{list-style:none;padding:0;display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(100%,220px),1fr))}
li,article{border:1px solid #767676;border-radius:8px;padding:12px;min-width:0}svg{width:100%;max-width:100%;height:auto}
[role=dialog]{position:fixed;inset:10% 5%;background:#fff;border:2px solid #1a1a1a;padding:16px;overflow:auto}[hidden]{display:none!important}
table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #767676;padding:4px}</style></head>
<body><main>${body}</main><script>${script}</script></body></html>`;

export const analytics = page('Pulseboard harness', `
<h1>Pulseboard</h1><p>Sample data — fixed harness numbers.</p>
<label for="range">Date range</label> <select id="range"><option>Last 7 days</option><option>Last 30 days</option></select>
<label for="region">Region</label> <select id="region"><option>All regions</option><option>North</option><option>South</option></select>
<section aria-label="Key metrics"><h2>Key metrics</h2><p>Revenue <strong id="m0"></strong></p><p>Orders <strong id="m1"></strong></p>
<p>Average order <strong id="m2"></strong></p><p>Conversion <strong id="m3"></strong></p></section>
<svg id="chart" role="img" aria-label="Revenue trend for the selected filters" viewBox="0 0 200 60"><polyline id="line" fill="none" stroke="#1a1a1a" stroke-width="2"/></svg>
<table aria-label="Top products"><thead><tr><th>Product</th><th>Units</th></tr></thead><tbody id="rows"></tbody></table>`, `
const data={'Last 7 days':[5,9,7,12,10,14,11],'Last 30 days':[30,42,38,51,47,60,55]},factor={'All regions':1,North:.6,South:.4};
const range=document.getElementById('range'),region=document.getElementById('region');
function render(){const f=factor[region.value],series=data[range.value].map(v=>Math.round(v*f*10));const revenue=series.reduce((a,b)=>a+b,0)*10,orders=series.reduce((a,b)=>a+b,0);
document.getElementById('m0').textContent='$'+revenue.toLocaleString('en-US');document.getElementById('m1').textContent=orders;
document.getElementById('m2').textContent='$'+(revenue/orders).toFixed(2);document.getElementById('m3').textContent=(2.1*f+range.selectedIndex).toFixed(1)+'%';
const max=Math.max(...series);document.getElementById('line').setAttribute('points',series.map((v,i)=>(i*30+10)+','+(55-v/max*50)).join(' '));
document.getElementById('rows').innerHTML=['Fern pot','Moss kit','Cactus trio'].map((n,i)=>'<tr><td>'+n+'</td><td>'+Math.round(orders/(i+2))+'</td></tr>').join('');}
range.onchange=render;region.onchange=render;render();`);

export const storefront = page('Fernwood harness', `
<h1>Fernwood</h1><p>Sample catalog — no real checkout.</p>
<label for="q">Search products</label> <input id="q" type="search">
<label for="cat">Category</label> <select id="cat"><option>All categories</option><option>Plants</option><option>Pots</option></select>
<button type="button" id="cartButton">Cart (0)</button>
<p id="empty" hidden>No products match. <button type="button" id="clear">Clear filters</button></p>
<ul aria-label="Products" id="list"></ul>
<div role="dialog" aria-modal="true" aria-labelledby="dTitle" id="details" hidden><h2 id="dTitle"></h2><p id="dPrice"></p><button type="button" id="dClose">Close</button></div>
<div role="dialog" aria-modal="true" aria-label="Shopping cart" id="cart" hidden><h2>Shopping cart</h2><ul id="cartItems"></ul><p>Subtotal <strong id="subtotal"></strong></p><button type="button" id="cClose">Close</button></div>`, `
const products=[['Fern','Plants',12.5],['Monstera','Plants',24],['Snake plant','Plants',18],['Clay pot','Pots',9.25],['Glazed pot','Pots',15],['Hanging pot','Pots',11]].map(([name,category,price],id)=>({id,name,category,price}));
let cart=[];try{cart=JSON.parse(localStorage.getItem('fernwood-cart')||'[]')}catch{}
let invoker=null;const $=id=>document.getElementById(id),money=v=>'$'+v.toFixed(2);
function save(){try{localStorage.setItem('fernwood-cart',JSON.stringify(cart))}catch{}}
function render(){const q=$('q').value.toLowerCase(),c=$('cat').value;const shown=products.filter(p=>p.name.toLowerCase().includes(q)&&(c==='All categories'||p.category===c));
$('list').innerHTML=shown.map(p=>'<li><h2>'+p.name+'</h2><p>'+p.category+'</p><p>'+money(p.price)+'</p><button type="button" data-add="'+p.id+'">Add to cart</button> <button type="button" data-view="'+p.id+'">View details</button></li>').join('');
$('empty').hidden=shown.length>0;$('cartButton').textContent='Cart ('+cart.length+')';
$('cartItems').innerHTML=cart.map((id,i)=>'<li>'+products[id].name+' '+money(products[id].price)+' <button type="button" data-remove="'+i+'">Remove</button></li>').join('');
$('subtotal').textContent=money(cart.reduce((s,id)=>s+products[id].price,0));}
function open(dialog,from){invoker=from;dialog.hidden=false;dialog.querySelector('button').focus();}
function close(){for(const d of document.querySelectorAll('[role=dialog]'))d.hidden=true;invoker?.focus();}
document.addEventListener('click',e=>{const t=e.target;if(t.dataset.add){cart.push(+t.dataset.add);save();render();}
if(t.dataset.view){const p=products[+t.dataset.view];$('dTitle').textContent=p.name;$('dPrice').textContent=money(p.price);open($('details'),t);}
if(t.dataset.remove){cart.splice(+t.dataset.remove,1);save();render();$('cClose').focus();}});
$('cartButton').onclick=e=>open($('cart'),e.target);$('dClose').onclick=close;$('cClose').onclick=close;
document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
$('q').oninput=render;$('cat').onchange=render;$('clear').onclick=()=>{$('q').value='';$('cat').value='All categories';render();};render();`);

export const social = page('Kestrel harness', `
<header><h1>Mai Tran</h1><p>Sample profile — landscape photographer, Da Lat.</p>
<p><span id="followers"></span> followers · 87 following</p><button type="button" id="follow" aria-pressed="false">Follow</button></header>
<label for="composer">Write a post</label><br><textarea id="composer" rows="3"></textarea><br><button type="button" id="post">Post</button>
<section aria-label="Posts" id="feed"></section>`, `
const $=id=>document.getElementById(id);let state={followers:1204,following:false,posts:[{id:'p1',text:'Morning fog over the pine hills.',likes:3,liked:false},{id:'p2',text:'Golden hour at the lake.',likes:8,liked:false}]};
try{const saved=JSON.parse(localStorage.getItem('kestrel')||'null');if(saved)state=saved}catch{}
function save(){try{localStorage.setItem('kestrel',JSON.stringify(state))}catch{}}
function render(){$('followers').textContent=state.followers.toLocaleString('en-US');$('follow').setAttribute('aria-pressed',String(state.following));
$('feed').innerHTML=state.posts.map(p=>'<article><p>'+p.text+'</p><button type="button" aria-pressed="'+p.liked+'" data-like="'+p.id+'">Like ('+p.likes+')</button></article>').join('');}
$('follow').onclick=()=>{state.following=!state.following;state.followers+=state.following?1:-1;save();render();};
$('post').onclick=()=>{const text=$('composer').value.trim();if(!text)return;state.posts.unshift({id:'p'+Date.now(),text,likes:0,liked:false});$('composer').value='';save();render();};
$('feed').onclick=e=>{const id=e.target.dataset.like;if(!id)return;const p=state.posts.find(x=>x.id===id);p.liked=!p.liked;p.likes+=p.liked?1:-1;save();render();};render();`);
