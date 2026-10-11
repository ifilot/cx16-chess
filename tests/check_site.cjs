/* Real browser QA: npm install --prefix build/browser-tools playwright@1.64.0
 * NODE_PATH="$PWD/build/browser-tools/node_modules" node tests/check_site.cjs
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const site = path.join(root, 'build/site');
const captures = path.join(root, 'build/site-check');
fs.mkdirSync(captures, {recursive:true});
const mime = {'.html':'text/html','.js':'text/javascript','.css':'text/css','.wasm':'application/wasm',
  '.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ttf':'font/ttf'};
const server = http.createServer((request,response) => {
  const url = new URL(request.url, 'http://localhost');
  if (!url.pathname.startsWith('/cx16-chess/')) {response.writeHead(404).end();return;}
  const name = path.resolve(site, '.' + url.pathname.slice('/cx16-chess'.length), url.pathname.endsWith('/')?'index.html':'');
  if (!name.startsWith(site+path.sep) || !fs.existsSync(name)) {response.writeHead(404).end();return;}
  response.setHeader('Content-Type', mime[path.extname(name)] || 'application/octet-stream');
  response.end(fs.readFileSync(name));
});
function python(code, args) {
  const result = spawnSync('python3', ['-c', code, ...args], {encoding:'utf8'});
  assert(!result.error, result.error?.message);
  return result;
}
async function captureScene(page, name, reference, box) {
  const file = path.join(captures, name+'.png');
  const deadline = Date.now()+45000;
  while (true) {
    // Chromium rounds fractional screenshot clips outward. Align the canvas
    // itself while comparing native pixels, as in Kakuro's browser check.
    await page.locator('#canvas').evaluate(element=>{
      const rect=element.getBoundingClientRect();
      element.style.transform=`translate(${Math.ceil(rect.x)-rect.x}px, ${Math.ceil(rect.y)-rect.y}px)`;
    });
    await page.locator('#canvas').screenshot({path:file});
    await page.locator('#canvas').evaluate(element=>{element.style.transform='';});
    const result = python(`
import sys,numpy as np
from PIL import Image
actual=np.asarray(Image.open(sys.argv[1]).convert('RGB'))
expected=np.asarray(Image.open(sys.argv[2]).convert('RGB'))
x,y,w,h=map(int,sys.argv[3:])
assert actual.shape==(480,640,3),actual.shape
assert np.array_equal(actual[y:y+h,x:x+w],expected[y:y+h,x:x+w]),'Scene pixels differ'
`, [file,path.join(root,'build/graphics',reference+'.png'),...box.map(String)]);
    if (result.status===0) return;
    if (Date.now()>=deadline) assert.fail(`${name} failed to render. ${result.stderr}`);
    await page.waitForTimeout(300);
  }
}
async function boot(page) {
  await page.click('#play');
  await page.waitForFunction(()=>typeof FS!=='undefined' && Module.calledRun && !document.querySelector('#canvas').hidden);
  await captureScene(page,'start','splash',[48,8,544,72]);
}
async function key(page, name) {
  await page.locator('#canvas').press(name,{delay:100});
  await page.waitForTimeout(200);
}
async function move(page,x,y) {
  const box=await page.locator('#canvas').boundingBox();
  await page.mouse.move(box.x+x,box.y+y);
  await page.waitForFunction(()=>mouseAligned && !mouseAligning);
  await page.waitForTimeout(400);
}
async function clickBoard(page,x,y) {
  await move(page,x,y);
  await page.mouse.down();await page.waitForTimeout(100);await page.mouse.up();
  await page.waitForTimeout(300);
}
function assertPawnMove(file) {
  const result=python(`
import sys,numpy as np
from PIL import Image
from pathlib import Path
sys.path.insert(0,sys.argv[2])
from build_graphics import square_image,blit,load_indexed,ASSETS
from palette import rgb
actual=np.asarray(Image.open(sys.argv[1]).convert('RGB'))
empty=square_image('NEWSPRINT',True,'LASTMOVE')
pawn=empty.copy()
blit(pawn,0,0,load_indexed(ASSETS/'pieces/victorian.png')[:,:56])
colors=np.array([rgb(i) for i in range(16)],np.uint8)
assert np.array_equal(actual[344:400,248:304],colors[empty]),'e2 is not empty with the last-move highlight'
assert np.array_equal(actual[232:288,248:304],colors[pawn]),'Pawn did not arrive on e4'
`,[file,path.join(root,'assets/scripts')]);
  assert.equal(result.status,0,result.stderr);
}
(async () => {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || undefined,
      args:['--enable-unsafe-swiftshader']});
    const page=await browser.newPage({viewport:{width:1280,height:1000}});
    const errors=[], failed=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('response',response=>{if(response.status()>=400)failed.push(response.url());});
    const address=`http://127.0.0.1:${server.address().port}/cx16-chess/`;
    await page.goto(address);
    await page.evaluate(()=>document.fonts.ready);
    assert.equal(await page.locator('h1').textContent(),'CX16 CHESS');
    assert.equal(await page.locator('tbody tr').count(),3);
    const summary=JSON.parse(fs.readFileSync(path.join(site,'research/summary.json')));
    for(const [index,level] of ['easy','normal','hard'].entries()) {
      const row=page.locator('tbody tr').nth(index);
      assert.equal(await row.locator('td').nth(2).textContent(),String(summary.summaries[level].estimated_elo));
    }
    assert.match(await page.locator('#strength').textContent(),/does not establish a clear strength ordering/);
    assert.equal(await page.locator('#canvas').isVisible(),false);
    assert.equal(await page.evaluate(()=>typeof Module.calledRun),'undefined','Emulator should load only on Play');
    await page.screenshot({path:path.join(captures,'website.png'),fullPage:true});
    await boot(page);
    const manifest=JSON.parse(fs.readFileSync(path.join(site,'game/manifest.json')));
    assert.deepEqual(manifest.resources,['CHESS.DAT','CHESS.PRG','MENU.BIN','UI.BIN']);
    const loaded=await page.evaluate(()=>FS.readdir('/'));
    for(const file of manifest.resources)assert(loaded.includes(file),`${file} missing from emulator filesystem`);
    assert(!loaded.includes('CHESSOPT.DAT'),'Developer preferences leaked into browser game');
    await key(page,'a');
    await captureScene(page,'about','about',[0,8,616,128]);
    await key(page,'Escape');
    await captureScene(page,'returned','splash',[48,8,544,72]);
    await key(page,'o');
    await captureScene(page,'options','options',[488,8,144,128]);
    await key(page,'Escape');
    await captureScene(page,'returned-options','splash',[48,8,544,72]);
    await key(page,'n');
    await captureScene(page,'setup','setup',[0,8,616,128]);
    for(let i=0;i<3;i++)await key(page,'ArrowRight'); // White -> Black -> CPU vs CPU -> Two Players
    await key(page,'Enter');
    await captureScene(page,'game','playfield-info',[488,8,144,32]);
    await move(page,639,479);
    await page.locator('#canvas').screenshot({path:path.join(captures,'board-before.png')});
    await clickBoard(page,276,372); // e2
    await clickBoard(page,276,260); // e4
    await move(page,639,479);
    const after=path.join(captures,'board-after.png');
    await page.locator('#canvas').screenshot({path:after});
    assertPawnMove(after);
    await key(page,'Escape');
    await page.locator('#canvas').screenshot({path:path.join(captures,'paused.png')});
    await key(page,'Escape');
    await captureScene(page,'resumed','playfield-info',[488,8,144,32]);
    for(const [width,height,scale] of [[1920,1080,2],[1536,864,1]]) {
      await page.setViewportSize({width,height});await page.waitForTimeout(200);
      assert.equal((await page.locator('#canvas').boundingBox()).width,640);
      await page.click('#fullscreen');
      await page.waitForFunction(()=>document.fullscreenElement?.id==='player');await page.waitForTimeout(200);
      const box=await page.locator('#canvas').boundingBox();
      assert.equal(box.width,640*scale);assert.equal(box.height,480*scale);
      const file=path.join(captures,`fullscreen-${width}.png`);
      await page.locator('#canvas').screenshot({path:file});
      const pixels=python(`
import sys,numpy as np
from PIL import Image
p=np.asarray(Image.open(sys.argv[1]).convert('RGB'));k=int(sys.argv[2])
assert p.shape==(480*k,640*k,3)
blocks=p.reshape(480,k,640,k,3)
assert np.all(blocks==blocks[:,0:1,:,0:1,:]),'Pixel scaling introduces interpolation'
`,[file,String(scale)]);
      assert.equal(pixels.status,0,pixels.stderr);
      await page.evaluate(()=>document.exitFullscreen());await page.waitForTimeout(200);
    }
    await page.setViewportSize({width:390,height:900});await page.waitForTimeout(200);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile layout overflows');
    assert(await page.locator('#touch-keys').isVisible());
    await page.screenshot({path:path.join(captures,'mobile.png'),fullPage:true});
    await page.close();

    const mobile=await browser.newContext({viewport:{width:844,height:1000},hasTouch:true,isMobile:true});
    const phone=await mobile.newPage();
    phone.on('pageerror',error=>errors.push(error.message));
    await phone.goto(address);await boot(phone);
    await phone.setViewportSize({width:390,height:844});
    assert(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await phone.locator('[data-key="Enter"]').tap();
    await phone.setViewportSize({width:844,height:1000});
    await captureScene(phone,'touch-setup','setup',[344,48,272,48]);
    for(let i=0;i<3;i++){await phone.locator('[data-key="ArrowRight"]').tap();await phone.waitForTimeout(150);}
    await phone.locator('[data-key="Enter"]').tap();
    await captureScene(phone,'touch-game','playfield-info',[488,8,144,32]);
    await phone.setViewportSize({width:390,height:844});
    await phone.locator('#game-viewport').scrollIntoViewIfNeeded();
    await phone.locator('#game-viewport').evaluate(element=>{element.scrollLeft=150;});
    const beforePan=await phone.locator('#game-viewport').evaluate(element=>element.scrollLeft);
    const viewportBox=await phone.locator('#game-viewport').boundingBox();
    const cdp=await mobile.newCDPSession(phone);
    const touch=(type,x)=>cdp.send('Input.dispatchTouchEvent',{type,
      touchPoints:type==='touchEnd'?[]:[{x,y:viewportBox.y+100}]});
    await touch('touchStart',viewportBox.x+60);
    for(let i=1;i<=8;i++){await touch('touchMove',viewportBox.x+60+i*25);await phone.waitForTimeout(30);}
    await touch('touchEnd');await phone.waitForTimeout(400);
    assert((await phone.locator('#game-viewport').evaluate(element=>element.scrollLeft))<beforePan,'Swipe does not pan the board');
    await phone.setViewportSize({width:844,height:1000});await phone.waitForTimeout(200);
    let box=await phone.locator('#canvas').boundingBox();
    // Rapid selection/destination taps arrive while initial pointer alignment
    // is still running. Both must be processed, in order.
    await phone.touchscreen.tap(box.x+276,box.y+372);
    await phone.touchscreen.tap(box.x+276,box.y+260);
    await phone.waitForFunction(()=>pendingTouchTaps===0 && mouseAligned);
    await phone.locator('#canvas').screenshot({path:path.join(captures,'touch-moved.png')});
    await phone.touchscreen.tap(box.x+639,box.y+479);
    await phone.waitForFunction(()=>pendingTouchTaps===0);
    const touchBoard=path.join(captures,'touch-board.png');
    await phone.locator('#canvas').screenshot({path:touchBoard});
    assertPawnMove(touchBoard);
    await phone.locator('[data-key="Escape"]').tap();await phone.waitForTimeout(300);
    await phone.locator('#canvas').screenshot({path:path.join(captures,'touch-paused.png')});
    await phone.locator('[data-key="Escape"]').tap();
    await captureScene(phone,'touch-resumed','playfield-info',[488,8,144,32]);
    await mobile.close();
    assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
    console.log('PASS: real r49 WASM boot, clean runtime bundle, exact serif mastheads, legal mouse move, menus, resume, pixel-perfect fullscreen, mobile layout and touch keys under a project subpath; ratings match recorded results.');
  } finally {if(browser)await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
