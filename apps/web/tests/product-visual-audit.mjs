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
    const reduced = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
    // Stabilize pixels without waiting on transitions belonging to collapsed details.
    if (!reduced) await page.emulateMedia({reducedMotion:'reduce'});
    for (const width of [1440,375]) {
      await page.setViewportSize({width,height:1000});
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      await page.evaluate(() => scrollTo(0,0));
      const layout = await page.evaluate(() => ({overflow:document.documentElement.scrollWidth>innerWidth,offenders:document.documentElement.scrollWidth<=innerWidth ? [] : [...document.querySelectorAll('main *')].filter(el=>el.getBoundingClientRect().right>innerWidth+1).map(el=>({tag:el.tagName,class:el.className,text:el.textContent?.slice(0,80)})).slice(-12)}));
      assert.deepEqual(layout,{overflow:false,offenders:[]},`${name} ${width}: page overflow`);
      if (width === 375 && await page.getByRole('navigation',{name:'Project navigation'}).count()) {
        assert.equal(await page.getByRole('navigation',{name:'Project navigation'}).evaluate(nav=>{const active=nav.querySelector('[aria-current=page]'),frame=nav.getBoundingClientRect(),item=active?.getBoundingClientRect();return Boolean(item&&item.left>=frame.left-1&&item.right<=frame.right+1);}),true,`${name}: current mobile navigation tab is visible`);
      }
      if (await page.locator('.workspace-preview').count()) assert.ok(await page.locator('.workspace-preview .button-primary:visible:not(:disabled)').count()<=1,`${name}: one primary workspace action`);
      if (axe && scan) {
        await page.addScriptTag({content:axe});
        assert.deepEqual(await page.evaluate(async()=> (await axe.run(document,{iframes:false,runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))),[],`${name} ${width}: accessibility`);
      }
      await page.screenshot({path:`${directory}/${name}-${width}.png`,fullPage:true});
      await page.screenshot({path:`${directory}/${name}-${width}-viewport.png`});
      measurements.push({reflowWidths:[320,720,768,1280],route:new URL(page.url()).pathname,state:name,width,overflow:false,accessibility:axe&&scan?'passed':'not_run'});
    }
    for (const width of [320,720,768,1280]) {
      await page.setViewportSize({width,height:width===720?500:1000});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${name} ${width}: page overflow`);
    }
    await page.setViewportSize({width:1440,height:1000});
    if (!reduced) await page.emulateMedia({reducedMotion:'no-preference'});
  }
  return {capture, finish:async()=>{if(enabled)await writeFile(`${directory}/audit.json`,JSON.stringify({measurements},null,2));}};
}
