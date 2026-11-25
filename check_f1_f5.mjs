import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const req=createRequire(import.meta.url);
const {chromium}=req('playwright');
const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'ko-KR'});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const checks=[];
const step=async (i,pattern)=>{await page.locator('#steps button').nth(i).click();await page.waitForFunction(p=>document.querySelector('#app').textContent.includes(p),pattern);};
try {
  await page.goto(pathToFileURL(process.cwd()+'/frontend/f3-f5/app.html').href+'?api='+encodeURIComponent(process.env.TEST_API_URL||'http://127.0.0.1:8888'));
  await page.waitForFunction(()=>document.querySelector('#app h1')?.textContent==='실행 목록');
  await page.locator('select[aria-label="Run"]').selectOption('RUN-PILOT6-V11-A-PREVIEW');
  await page.waitForFunction(()=>document.querySelector('#app h1')?.textContent==='실행 목록'&&document.querySelector('#app .kv')?.textContent.includes('prompt_v11_a'));
  assert.match(await page.locator('#app').textContent(),/검토용 · 추론 미실행/);checks.push('F1 versioned preview');
  await page.screenshot({path:'F1_v11.png',fullPage:true});
  await page.getByRole('button',{name:'+ 새 실행',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.picks')?.querySelectorAll('input').length===12);checks.push('F1 prompt and candidate catalog');
  await page.getByRole('button',{name:'닫기',exact:true}).click();
  await step(1,'관계 9칸 F1');assert.match(await page.locator('#app').textContent(),/성능 표가 아닙니다/);assert.match(await page.locator('#app').textContent(),/보조 항목/);checks.push('F2 9 cells and 4 auxiliary metrics');
  await page.screenshot({path:'F2_v11.png',fullPage:true});
  await step(2,'검토 문항 목록');assert.equal(await page.locator('#app button.item').count(),6);checks.push('F3 six draft items');
  await page.screenshot({path:'F3_v11.png',fullPage:true});
  await step(3,'모델 비교');assert.match(await page.locator('#app').textContent(),/비교 불가/);
  /* Base 후보 = 같은 v1.1 Run만 (work/backend-1125부터 실제 v11_a/b가 추가돼 2개 이상) */
  assert.equal(await page.locator('select[aria-label="Base"] option').count(),await page.evaluate(()=>api.runs.filter(r=>r.schema_version==='1.1-review').length));checks.push('F4 only same-version runs');
  await page.screenshot({path:'F4_v11.png',fullPage:true});
  await step(2,'검토 문항 목록');await page.locator('button.item').filter({hasText:'pilot_002'}).click();
  await page.waitForFunction(()=>document.querySelector('.stage')?.dataset.imageState==='loaded');
  assert.equal(await page.locator('.tabs button').count(),3);assert.ok(await page.locator('.stage svg polygon').count()>0);assert.match(await page.locator('#app').textContent(),/객체 위치·방향/);
  await page.getByRole('button',{name:/측방 가림/}).click();assert.match(await page.locator('#app').textContent(),/측방의 필요한 연결/);checks.push('F5 real image, polygon, R1-R3, auxiliary navigation');
  await page.getByRole('button',{name:/R1점유/}).click().catch(()=>page.locator('.tabs button').first().click());
  await page.screenshot({path:'F5_Pilot002_v11.png',fullPage:true});
  await page.locator('select[aria-label="Run"]').selectOption('RUN-PILOT6-BASE-001');
  await step(1,'관계 12칸 F1');checks.push('legacy v1.0 preserved');
  /* 새 v1.1 Run(실제 추론 A): 보조 4개 줄과 형식 오류 원문 */
  if(await page.locator('select[aria-label="Run"] option[value="v11_a_e18f74ffcc"]').count()){
    await page.locator('select[aria-label="Run"]').selectOption('v11_a_e18f74ffcc');await step(2,'오류 목록');
    assert.equal(await page.locator('#app button.item .aux').first().locator('.ax').count(),4);
    await page.locator('button.item').filter({hasText:'pilot_003'}).click();await page.waitForFunction(()=>document.querySelector('#app').textContent.includes('모델 원문'));checks.push('v1.1 real run: auxiliary row, raw output');}
  /* T2 Track 2: 서버에 Track 2 API가 없으면 임시 예시로 확인 */
  await page.locator('#steps button').filter({hasText:'영상'}).click();
  await page.waitForFunction(()=>/Track 2/.test(document.querySelector('#app').textContent));
  if(await page.getByRole('button',{name:'임시 예시로 보기'}).count())await page.getByRole('button',{name:'임시 예시로 보기'}).click();
  await page.waitForFunction(()=>document.querySelector('#t2badge')?.textContent.includes('판단 시점'));
  assert.ok(await page.locator('#t2svg rect').count()>0);assert.ok(await page.locator('.tl .dc').count()>0);checks.push('T2 decision point, boxes, timeline');
  assert.deepEqual(errors,[]);
  await writeFile('browser_verification.json',JSON.stringify({checks,errors},null,2));
  console.log(checks.join('\n'));
} finally {await browser.close();}
