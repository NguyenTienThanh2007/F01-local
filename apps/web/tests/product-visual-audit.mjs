import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';

// Opt-in route inspection runs inside the actual signed-in commercial journey.
export async function productVisualAudit(page, directory) {
  const enabled = process.env.F01_VISUAL_AUDIT === '1', measurements = [];
  if (enabled) await mkdir(directory, {recursive:true});
  const axe = enabled && process.env.M5_AXE_SCRIPT ? await readFile(process.env.M5_AXE_SCRIPT,'utf8') : null;
  async function capture(name, {scan=true}={}) {
    if (!enabled) return;
    if (await page.locator('iframe').count()) {
      await page.getByText('Loading your application preview…',{exact:true}).waitFor({state:'hidden'});
    }
    for (const width of [1440,375]) {
      await page.setViewportSize({width,height:1000});
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        await Promise.all(document.getAnimations().filter(animation => animation.constructor.name === 'CSSTransition').map(animation => animation.finished.catch(() => {})));
      });
      await page.evaluate(() => scrollTo(0,0));
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth ? [] : [...document.querySelectorAll('main *')].filter(el=>el.getBoundingClientRect().right>innerWidth+1).map(el=>({tag:el.tagName,class:el.className,text:el.textContent?.slice(0,80)})).slice(-12));
      assert.deepEqual(overflow,[],`${name} ${width}: page overflow`);
      if (axe && scan) {
        await page.addScriptTag({content:axe});
        assert.deepEqual(await page.evaluate(async()=> (await axe.run(document,{iframes:false,runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))),[],`${name} ${width}: accessibility`);
      }
      await page.screenshot({path:`${directory}/${name}-${width}.png`,fullPage:true});
      measurements.push({route:new URL(page.url()).pathname,state:name,width,overflow:false,accessibility:axe&&scan?'passed':'not_run'});
    }
    for (const width of [768,1280]) {
      await page.setViewportSize({width,height:1000});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${name} ${width}: page overflow`);
    }
    await page.setViewportSize({width:1440,height:1000});
  }
  return {capture, finish:async()=>{if(enabled)await writeFile(`${directory}/audit.json`,JSON.stringify({measurements},null,2));}};
}
