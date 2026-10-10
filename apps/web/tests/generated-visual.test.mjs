import test from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {collectVisualMetrics,assessVisualMetrics,auditGeneratedEditor,auditGeneratedPage} from './generated-visual-acceptance.mjs';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

test('browser metric regression reproduces vertical flex-basis growth and below-fold content',async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    // Minimal faithful regression fixture, never a generated-app acceptance substitute.
    await page.setContent(`<style>body{font:16px system-ui}.group{display:flex;flex-direction:column}.input{flex:1 1 150px;padding:8px 12px}.form{display:flex;flex-direction:column;gap:16px}</style><main><h1>Fixture</h1><div class="form">${Array.from({length:4},(_,i)=>`<div class="group"><label for="f${i}">Field</label><input id="f${i}" class="input"></div>`).join('')}</div><section id="board">Working board</section></main>`);
    const metrics=await page.evaluate(collectVisualMetrics,{primarySelector:'#board'});
    assert.ok(metrics.controls.every(c=>c.height>=150));
    assert.equal(metrics.controls[0].parentAxis,'column');
    const result=assessVisualMetrics(metrics,{requirePrimary:true});
    assert.equal(result.deterministicPassed,false);
    assert.equal(result.checks.find(c=>c.name.startsWith('Single-line')).passed,false);
    assert.equal(result.checks.find(c=>c.name.startsWith('Primary')).passed,false);
  } finally {await browser.close();}
});

test('an inert primary action fails editor acceptance instead of certifying its good-looking board',async()=>{
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'f01-editor-visual-'));
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage();
    await page.setContent('<main><h1>Fixture</h1><button>New Task</button></main>');
    const result=await auditGeneratedEditor(page,{directory,actionName:'New Task',timeout:200});
    assert.equal(result.opened,false);
    assert.equal(result.deterministicPassed,false);
    assert.equal(result.accessibilityPassed,null);
    assert.ok((await fs.stat(path.join(directory,'action-failed.png'))).size>0);
  } finally {await browser.close();await fs.rm(directory,{recursive:true,force:true});}
});

test('actual browser QA detects overflowing nowrap card metadata and insufficient badge contrast',async()=>{
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'f01-card-visual-'));
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage();
    // Faithful sizing/contrast regression fixture, not an OpenAI application.
    await page.setContent(`<html lang="en"><head><title>Card regression</title><style>body{margin:0;font:16px system-ui}main{padding:24px}.card{width:100%;display:flex;gap:8px}h2{margin:0;overflow-wrap:break-word}.metadata{flex-shrink:0;white-space:nowrap;color:#e53e3e;background:#fed7d7}</style></head><body><main><h1>Fixture</h1><section id="board"><div class="card"><h2>Long title</h2><span class="metadata">High priority · 2026-10-09 (Overdue)</span></div></section></main></body></html>`);
    const result=await auditGeneratedPage(page,{directory,primarySelector:'#board',viewports:[{name:'mobile',width:320,height:800}]});
    assert.equal(result.deterministicPassed,false);
    assert.equal(result.states[0].checks.find(c=>c.name==='No page horizontal overflow').passed,false);
    assert.equal(result.accessibilityPassed,false);
    assert.ok(result.states[0].accessibility.violations.some(v=>v.id==='color-contrast'));
    assert.ok((await fs.stat(path.join(directory,'mobile.png'))).size>0);
  } finally {await browser.close();await fs.rm(directory,{recursive:true,force:true});}
});

test('responsive compact layout passes measurements without claiming subjective quality',async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage();
    await page.setContent(`<style>*{box-sizing:border-box}body{margin:0;font:16px system-ui}main{padding:16px}input{width:100%;height:40px;font:16px system-ui}.filters{display:grid;gap:8px;grid-template-columns:minmax(0,1fr)}#board{margin-top:16px}</style><main><h1>Different fixture</h1><div class="filters"><label for="search">Search</label><input id="search"></div><section id="board">Primary content</section></main>`);
    for(const width of [1440,768,390,320]) {
      await page.setViewportSize({width,height:844});
      const result=assessVisualMetrics(await page.evaluate(collectVisualMetrics,{primarySelector:'#board'}),{requirePrimary:true});
      assert.equal(result.deterministicPassed,true);
    assert.ok(result.subjectiveReviewRequired.some(s=>s.includes('do not certify premium')));
    }
    await page.addStyleTag({content:'main{min-width:1500px}'});
    const result=assessVisualMetrics(await page.evaluate(collectVisualMetrics,{primarySelector:'#board'}));
    assert.equal(result.checks.find(c=>c.name==='No page horizontal overflow').passed,false);
    await page.setContent(`<main>${Array.from({length:81},()=>'<input aria-label="Fixture">').join('')}</main>`);
    const bounded=assessVisualMetrics(await page.evaluate(collectVisualMetrics,{primarySelector:'#missing'}),{requirePrimary:true});
    assert.equal(bounded.checks.find(c=>c.name==='Bounded control coverage is complete').passed,false);
    assert.equal(bounded.checks.find(c=>c.name.startsWith('Primary')).passed,false);
  } finally {await browser.close();}
});
