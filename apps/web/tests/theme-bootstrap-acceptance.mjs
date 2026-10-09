import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';

export async function verifyThemeBootstrap(browser, base, directory) {
  await mkdir(directory, {recursive:true});
  const evidence=[];
  for (const preference of ['light','dark','system']) {
    const context=await browser.newContext({colorScheme:'dark'});
    try {
      await context.addInitScript(preference=>{
        localStorage.setItem('f01.theme.v1',preference);
        window.__themeFrames=[];window.__themeControls=[];
        const sample=()=>{
          if(document.body){
            window.__themeFrames.push(document.documentElement.dataset.theme);
            for(const control of document.querySelectorAll('select[data-f01-theme-control]')) window.__themeControls.push(control.value);
          }
          if(window.__themeFrames.length<8)requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
      },preference);
      const page=await context.newPage();
      await page.route('**/_next/static/**/*.js',route=>route.abort());
      await page.goto(base,{waitUntil:'load'});
      await page.waitForFunction(()=>window.__themeFrames.length>=8);
      const expected=preference==='light'?'light':'dark';
      assert.deepEqual(await page.evaluate(()=>[...new Set(window.__themeFrames)]),[expected],'Every observed pre-hydration body frame uses the persisted theme.');
      assert.deepEqual(await page.evaluate(()=>[...new Set(window.__themeControls)]),[preference],'The appearance selector must also match before React loads.');
      assert.equal(await page.getByRole('combobox',{name:'Color theme',exact:true}).inputValue(),preference);
      await page.screenshot({path:`${directory}/before-hydration-${preference}.png`,fullPage:true});
      evidence.push({preference,expected,react:'blocked',body_frames:8,selector:'correct-before-hydration'});
    } finally {await context.close();}
  }
  return evidence;
}
