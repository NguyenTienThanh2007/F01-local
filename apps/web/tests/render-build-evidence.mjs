// Read-only visual fixtures of actual components. No worker/Docker/provider acceptance.
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {join,dirname} from 'node:path';
import assert from 'node:assert/strict';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {observeBuild} from '../src/lib/workspace/build-progress.ts';
import {projectJourney} from '../src/lib/workspace/journey.ts';
import * as f from './build-observation-fixtures.mjs';
const web=fileURLToPath(new URL('../',import.meta.url)),repo=dirname(dirname(web)),out=join(repo,'QA/build-journey/local-render');
await mkdir(out,{recursive:true});
async function compile(name){const source=await readFile(join(web,'src/features/workspace/'+name+'.tsx'),'utf8');let js=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;js=js.replace(/['"]react\/jsx-runtime['"]/g,JSON.stringify(import.meta.resolve('react/jsx-runtime'))).replace(/['"]@\/lib\/workspace\/dates['"]/g,JSON.stringify(pathToFileURL(join(web,'src/lib/workspace/dates.ts')).href));return import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));}
const {BuildActivity,BuildTimeline}=await compile('build-progress'),{JourneyRail}=await compile('journey-rail');
let css='';for(const name of await readdir(join(web,'.next/static/css')))if(name.endsWith('.css'))css+=await readFile(join(web,'.next/static/css',name),'utf8');
for(const match of [...css.matchAll(/url\((?:['"])?([^)'" ]+\.woff2)(?:['"])?\)/g)]){try{const bytes=await readFile(join(web,'.next/static/media',match[1].split('/').at(-1)));css=css.replaceAll(match[0],`url(data:font/woff2;base64,${bytes.toString('base64')})`);}catch{}}
await writeFile(join(out,'styles.css'),css);
const cases=[
 ['queued',f.detail({run:f.run(),phase:'context_resolution'})],['understanding',f.detail({phase:'context_resolution'})],['generation-pending',f.detail()],
 ['building',f.detail({phase:'install',candidates:[f.candidate()],current_candidate_evidence:f.checks().slice(0,2)})],
 ['verifying',f.detail({phase:'build',candidates:[f.candidate()],current_candidate_evidence:f.checks().slice(0,4)})],
 ['repairing',f.detail({repair_attempts:1,candidates:[f.candidate()],evidence:f.checks(),current_candidate_evidence:[f.evidence('typecheck',1)]})],
 ['preparing-preview',f.detail({phase:'test',candidates:[f.candidate()],current_candidate_evidence:f.checks().slice(0,5)})],
 ['succeeded',f.detail({run:f.run({status:'succeeded'}),phase:'preview_ready',candidates:[f.candidate()],current_candidate_evidence:f.checks()})],
 ['failed',f.detail({run:f.run({status:'failed',error_code:'REPAIR_EXHAUSTED'})})],['canceled',f.detail({run:f.run({status:'canceled',error_code:'BUILD_CANCELED'})})],
 ['worker-stall',f.detail({run:f.run({status:'running',created_at:f.stamp(-95000),started_at:f.stamp(-90000),last_heartbeat_at:f.stamp(-60000)}),progress_updated_at:f.stamp(-60000)})],
 ['waiting-with-check-in',f.detail({run:f.run({status:'running',created_at:f.stamp(-95000),started_at:f.stamp(-90000),last_heartbeat_at:f.stamp(-1000)}),progress_updated_at:f.stamp(-60000)})],
 ['worker-recovery',f.detail({phase:'recovery',candidates:[f.candidate()],current_candidate_evidence:f.checks()})],
 ['update-live-preserved',f.detail({run:f.run({status:'running',started_at:f.stamp(-4000),last_heartbeat_at:f.stamp(-1000),base_version_id:f.ids.version})})],
];
for(const [name,d] of cases){
 const v=name==='succeeded'||name==='update-live-preserved'?f.version():null,live=name==='update-live-preserved'?f.release():null;
 const progress=observeBuild({run:d.run,detail:d,events:[],version:v,now:f.now});
 const journey=projectJourney({snapshot:f.snapshot({active_run:['queued','running'].includes(d.run.status)?d.run:null,latest_run:d.run,current_version:v}),plans:null,releases:live?f.releases({current_release_id:live.id,releases:[live]}):null,progress,now:f.now});
 const rail=renderToStaticMarkup(createElement(JourneyRail,{journey})),activity=renderToStaticMarkup(createElement(BuildActivity,{progress})),timeline=renderToStaticMarkup(createElement(BuildTimeline,{progress}));
 assert.equal((timeline.match(/<li /g)??[]).length,6);assert.equal((rail.match(/<li /g)??[]).length,6);
 if(['worker-stall','waiting-with-check-in','failed','canceled'].includes(name))assert.match(activity,/data-animated="false"/);
 if(name==='worker-stall')assert.match(activity,/Needs a status check/);
 const html=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>F01 · ${name} · rendering fixture</title><link rel="stylesheet" href="styles.css"><style>.fixture-label{padding:14px 24px;background:#212821;color:white;font:13px/1.6 sans-serif}.fixture-label a{color:white;text-decoration:underline}.evidence-app{max-width:1200px;margin:auto}.evidence-actions{display:flex;gap:16px}.evidence-app .project-header{padding-inline:40px}.evidence-app .workspace-canvas{min-width:0}@media(max-width:767px){.evidence-app .project-header{padding-inline:20px}.evidence-actions{display:block}}</style><div class="fixture-label"><strong>Component rendering fixture · ${name}</strong><br>Actual React presentation and CSS. No worker, Docker or provider executed. Controls are disabled. <a href="index.html">All states</a></div><main class="evidence-app" inert><div class="workspace-page"><header class="project-header"><div class="project-heading"><span class="meta">F01 / SOFTWARE FACTORY</span><h1>FocusFlow</h1></div></header><section class="journey-guide journey-v3" aria-label="Current project step" data-current="build" data-state="${journey.state}"><div class="journey-current"><span class="journey-kicker">${journey.update?'Update journey':'Project journey'} · Step ${journey.step+1} of 6</span><p><strong>${journey.title}</strong><span>${journey.next}</span></p></div>${rail}${live?'<div class="journey-live-preserved"><strong>Last confirmed live release · Version 1</strong><span>Stays recorded while this update progresses.</span></div>':''}</section><div class="workspace-canvas"><div class="build-pane focus-pane"><section class="workspace-notice build-command" aria-label="Real build">${activity}${timeline}<div class="evidence-actions"><button class="button button-primary" disabled>${progress.waiting?'Check saved build status':'Follow Build Trace'}</button><button class="button button-secondary" disabled>Cancel real build</button></div><details><summary>Build details and verification evidence</summary><p>Generated-contract fixture · checks are scoped to this attempt.</p></details></section></div></div></div></main></html>`;
 await writeFile(join(out,name+'.html'),html);
}
await writeFile(join(out,'index.html'),`<!doctype html><html lang="en"><meta charset="utf-8"><title>F01 build component review</title><style>body{font:18px/1.7 sans-serif;max-width:850px;margin:48px auto;padding:20px}li{margin:12px 0}</style><h1>F01 build component review</h1><p>Read-only fixtures of the actual React components and compiled CSS. Browser E2E, Docker and provider checks are separate gates.</p><ul>${cases.map(([name])=>`<li><a href="${name}.html">${name}</a></li>`).join('')}</ul></html>`);
console.info(`Rendered ${cases.length} fixtures at ${out}`);
