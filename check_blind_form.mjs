import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const req=createRequire(import.meta.url);
const {chromium}=req('playwright');
const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
const p=await browser.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
try {
  await p.goto(pathToFileURL(process.cwd()+'/data_v11/Pilot3_v11_Blind_Labeling.html').href);
  assert.equal(await p.locator('main section').count(),3);
  assert.equal(await p.locator('main select').count(),18);
  await p.waitForFunction(()=>Array.from(document.querySelectorAll('main img')).every(e=>e.naturalWidth>0));
  const sec=p.locator('main section').first();
  await sec.locator('select').nth(1).selectOption('A');
  assert.equal(await sec.locator('select').nth(2).inputValue(),'NA');
  assert.equal(await sec.locator('select').nth(2).isDisabled(),true);
  await sec.locator('select').nth(1).selectOption('P');
  assert.equal(await sec.locator('select').nth(2).isDisabled(),false);
  await sec.locator('select').nth(3).selectOption('P');
  await sec.locator('select').nth(4).selectOption('A');
  assert.match(await sec.locator('[data-rollup]').textContent(),/Y/);
  await p.locator('#show').click();
  const rows=(await p.locator('#json').inputValue()).split('\n').map(JSON.parse);
  assert.equal(rows.length,3);assert.equal(rows[0].fields.R3,'P');assert.equal(rows[0].annotator_kind,'human');
  assert.equal(await p.locator('section:first-child img').count(),1);
  assert.deepEqual(errors,[]);
  console.log('3 images; 6 input fields each; R2 NA gate, R3 automatic rollup and JSONL verified; no prefilled AI labels');
} finally {await browser.close();}
