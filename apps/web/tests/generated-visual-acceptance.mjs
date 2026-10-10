// Bounded browser evidence for generated apps. No source rewriting or model calls.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export const VIEWPORTS = Object.freeze([
  {name:'desktop', width:1440, height:900},
  {name:'tablet', width:768, height:1024},
  {name:'mobile', width:390, height:844},
  {name:'reflow', width:320, height:800},
]);

// Runs in the actual page. Keep bounded and observational; never alter app data.
export function collectVisualMetrics({primarySelector}) {
  const visible = element => {
    const rect=element.getBoundingClientRect(), style=getComputedStyle(element);
    return rect.width>0 && rect.height>0 && style.visibility!=='hidden' && style.display!=='none';
  };
  const dimensions = element => {
    const rect=element.getBoundingClientRect(), style=getComputedStyle(element);
    return {tag:element.tagName.toLowerCase(), type:element.getAttribute('type'),
      label:element.getAttribute('aria-label') || element.labels?.[0]?.textContent?.trim() || element.textContent?.trim().slice(0,80) || '',
      top:Math.round(rect.top), width:Math.round(rect.width), height:Math.round(rect.height),
      fontSize:parseFloat(style.fontSize), fontWeight:style.fontWeight,
      lineHeight:style.lineHeight, color:style.color, background:style.backgroundColor,
      flexBasis:style.flexBasis, parentAxis:element.parentElement ? getComputedStyle(element.parentElement).flexDirection : null};
  };
  const inputs=[...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=range]):not([type=color]),select')].filter(visible);
  const buttons=[...document.querySelectorAll('button')].filter(visible);
  const primary=primarySelector ? document.querySelector(primarySelector) : null;
  return {viewport:{width:innerWidth,height:innerHeight}, pageWidth:document.documentElement.scrollWidth,
    primary:primary && visible(primary) ? dimensions(primary) : null,
    coverage:{controls:inputs.length,buttons:buttons.length,truncated:inputs.length>80 || buttons.length>100},
    controls:inputs.slice(0,80).map(dimensions), buttons:buttons.slice(0,100).map(dimensions),
    textareas:[...document.querySelectorAll('textarea')].filter(visible).slice(0,20).map(dimensions),
    headings:[...document.querySelectorAll('h1,h2,h3')].filter(visible).slice(0,40).map(dimensions),
    landmarks:{main:document.querySelectorAll('main,[role=main]').length,nav:document.querySelectorAll('nav,[role=navigation]').length},
    focused:document.activeElement?.getAttribute('aria-label') || document.activeElement?.tagName || null};
}

export function assessVisualMetrics(metrics,{requirePrimary=false}={}) {
  const checks=[{name:'Bounded control coverage is complete',passed:metrics.coverage?.truncated!==true},
    {name:'No page horizontal overflow',passed:metrics.pageWidth<=metrics.viewport.width+2}];
  // Compact application profile, not a universal aesthetic or WCAG guarantee.
  checks.push({name:'Single-line controls stay compact (maximum 72px)',passed:metrics.controls.every(c=>c.height<=72)});
  checks.push({name:'Readable control text (at least 14px)',passed:metrics.controls.every(c=>c.fontSize>=14)});
  if(requirePrimary) checks.push({name:'Primary working content starts above the fold',passed:metrics.primary!==null && metrics.primary.top>=0 && metrics.primary.top<metrics.viewport.height*.7});
  const review=[];
  if(metrics.buttons.some(c=>c.height<44 || c.width<44)) review.push('Review smaller than 44px touch targets and surrounding spacing; WCAG minimum/exception needs context.');
  if(metrics.textareas.some(c=>c.height>192)) review.push('Review tall textareas against the actual writing task.');
  if(metrics.landmarks.main!==1) review.push('Review main landmark structure.');
  return {checks,deterministicPassed:checks.every(c=>c.passed),review,
    subjectiveReviewRequired:['Hierarchy and composition','Density and alignment','Cohesive typography/color','Useful empty/loading/error states','Product suitability; these measurements do not certify premium design']};
}

export async function auditGeneratedPage(page,{directory,primarySelector,viewports=VIEWPORTS}={}) {
  if(!directory || viewports.length<1 || viewports.length>4 || viewports.some(v=>!Number.isInteger(v.width) || !Number.isInteger(v.height) || v.width<240 || v.width>1920 || v.height<240 || v.height>1200 || !/^[a-z0-9-]+$/.test(v.name))) throw Error('Audit requires 1–4 bounded, named viewports.');
  await fs.mkdir(directory,{recursive:true});
  const report={profile:'compact application',states:[],deterministicPassed:true,accessibilityPassed:true};
  for(const viewport of viewports) {
    await page.setViewportSize({width:viewport.width,height:viewport.height});
    await page.evaluate(()=>Promise.race([document.fonts.ready,new Promise(resolve=>setTimeout(resolve,2000))]));
    const metrics=await page.evaluate(collectVisualMetrics,{primarySelector:primarySelector ?? null});
    const assessment=assessVisualMetrics(metrics,{requirePrimary:!!primarySelector});
    await page.addScriptTag({path:fileURLToPath(new URL('../node_modules/axe-core/axe.min.js',import.meta.url))});
    const accessibility=await page.evaluate(async()=>{
      let timeout;
      const result=await Promise.race([
        window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}),
        new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('Accessibility scan exceeded 10 seconds')),10000)}),
      ]).finally(()=>clearTimeout(timeout));
      return {violations:result.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,
        nodeCount:v.nodes.length,nodes:v.nodes.slice(0,20).map(n=>({target:n.target,failureSummary:n.failureSummary}))})),
        incomplete:result.incomplete.map(v=>({id:v.id,nodes:v.nodes.length}))};
    });
    await page.screenshot({path:path.join(directory,`${viewport.name}.png`),fullPage:false});
    report.states.push({name:viewport.name,metrics,...assessment,accessibility});
    report.deterministicPassed &&= assessment.deterministicPassed;
    report.accessibilityPassed &&= accessibility.violations.length===0;
  }
  await fs.writeFile(path.join(directory,'visual.json'),JSON.stringify(report,null,2));
  return report;
}

export async function auditGeneratedEditor(page,{directory,actionName,timeout=5000}={}) {
  if(!directory || !actionName || timeout<100 || timeout>5000) throw Error('A bounded editor action is required.');
  await page.setViewportSize({width:1440,height:900});
  await fs.mkdir(directory,{recursive:true});
  let opened=false;
  try {
    await page.getByRole('button',{name:actionName,exact:true}).click({timeout});
    await page.getByRole('dialog').waitFor({state:'visible',timeout});
    opened=true;
  } catch { /* Missing action/dialog is a recorded failed check, not success. */ }
  if(!opened) {
    await page.screenshot({path:path.join(directory,'action-failed.png'),fullPage:false});
    const result={opened:false,deterministicPassed:false,accessibilityPassed:null,checks:[{name:'Primary editor action opens a visible semantic dialog',passed:false}]};
    await fs.writeFile(path.join(directory,'visual.json'),JSON.stringify(result,null,2));
    return result;
  }
  const result=await auditGeneratedPage(page,{directory,viewports:VIEWPORTS.filter(v=>['desktop','mobile'].includes(v.name))});
  await page.keyboard.press('Escape');
  return {...result,opened:true};
}

// Exact URL comes from a private environment variable; never print its capability.
if(process.argv[1] && fileURLToPath(import.meta.url)===path.resolve(process.argv[1])) {
  let browser;
  try {
    const {chromium}=await import('playwright');
    const url=process.env.F01_GENERATED_PREVIEW_URL;
    if(!url) throw Error('Missing preview');
    const parsed=new URL(url);
    if(parsed.protocol!=='http:' || parsed.username || parsed.password || !(parsed.hostname==='localhost' || parsed.hostname.endsWith('.localhost'))) throw Error('Invalid local preview');
    const directory=process.env.F01_VISUAL_OUTPUT || '.runtime/generated-visual';
    browser=await chromium.launch({headless:true});
    const page=await browser.newPage();
    await page.goto(url,{waitUntil:'networkidle',timeout:20000});
    const report=await auditGeneratedPage(page,{directory,primarySelector:process.env.F01_PRIMARY_CONTENT_SELECTOR});
    const editor=process.env.F01_EDITOR_ACTION ? await auditGeneratedEditor(page,{directory:path.join(directory,'editor'),actionName:process.env.F01_EDITOR_ACTION}) : null;
    console.log(JSON.stringify({states:report.states.length,deterministicPassed:report.deterministicPassed,accessibilityPassed:report.accessibilityPassed,editor:editor ? {opened:editor.opened,deterministicPassed:editor.deterministicPassed,accessibilityPassed:editor.accessibilityPassed} : 'not tested',subjectiveReview:'required'}));
    if(!report.deterministicPassed || !report.accessibilityPassed || (editor && (!editor.deterministicPassed || !editor.accessibilityPassed))) process.exitCode=1;
  } catch {
    // Playwright navigation diagnostics can include private capability URLs.
    console.error('Visual audit could not complete. Check the private local preview URL, primary selector, readiness and installed Chromium.');
    process.exitCode=1;
  } finally {await browser?.close();}
}
