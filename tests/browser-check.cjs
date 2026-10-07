const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawn} = require('node:child_process');
const assert = require('node:assert/strict');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'cem-itx-chrome-'));
const chrome = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=9335', '--user-data-dir=' + profile, 'about:blank'], {windowsHide: true, stdio: 'ignore'});
let socket;
const errors = [];
async function main() {
  let pages;
  for (let i = 0; i < 60; i++) {
    try { pages = await fetch('http://127.0.0.1:9335/json').then(r=>r.json()); if (pages.length) break; } catch {}
    await sleep(200);
  }
  assert(pages?.length, 'Chrome ne répond pas');
  socket = new WebSocket(pages.find(x=>x.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let counter=0;
  const pending=new Map();
  socket.onmessage=event=>{
    const data=JSON.parse(event.data);
    if(data.id){const task=pending.get(data.id);pending.delete(data.id);if(data.error)task.reject(new Error(JSON.stringify(data.error)));else task.resolve(data.result);}
    if(data.method==='Runtime.exceptionThrown') errors.push(data.params.exceptionDetails.text);
  };
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++counter;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{
    const data=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(data.exceptionDetails)throw new Error(JSON.stringify(data.exceptionDetails));
    return data.result.value;
  };
  const until=async expression=>{for(let i=0;i<120;i++){if(await evaluate(expression))return;await sleep(100);}throw new Error('Timeout: '+expression);};
  await call('Runtime.enable');
  await call('Network.enable');
  await call('Network.clearBrowserCookies');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:'http://127.0.0.1:5000/'});
  await until(`document.getElementById('word') && !document.getElementById('word').disabled`);
  assert.equal(await evaluate(`document.getElementById('attempt-count').textContent`),'0');
  const submit=async word=>{
    await evaluate(`document.getElementById('word').value=${JSON.stringify(word)};document.getElementById('guess-form').requestSubmit()`);
    await until(`!document.getElementById('submit-button').disabled || !document.getElementById('victory').hidden`);
  };
  await submit('école');
  assert.equal(await evaluate(`document.getElementById('attempt-count').textContent`),'1');
  await submit('ÉCOLE');
  assert.equal(await evaluate(`document.getElementById('attempt-count').textContent`),'1');
  assert((await evaluate(`document.getElementById('message').textContent`)).includes('déjà'));
  await submit('zzzinconnu');
  assert.equal(await evaluate(`document.getElementById('attempt-count').textContent`),'1');
  assert(await evaluate(`document.getElementById('message').classList.contains('error')`));
  await submit('nature');
  assert.equal(await evaluate(`document.getElementById('attempt-count').textContent`),'2');
  await evaluate(`document.getElementById('sort-button').click()`);
  assert.equal(await evaluate(`document.querySelector('#attempts tr td:nth-child(2)').textContent`),'nature');
  await call('Page.reload');
  await until(`document.getElementById('attempt-count')?.textContent === '2'`);
  await evaluate(`document.getElementById('help-button').click()`);
  assert(await evaluate(`document.getElementById('rules-dialog').open`));
  await evaluate(`document.getElementById('close-rules').click()`);
  assert.equal(await evaluate(`document.getElementById('rules-dialog').open`),false);
  const artifacts=path.resolve('artifacts');fs.mkdirSync(artifacts,{recursive:true});
  const screenshot=async name=>{const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(artifacts,name),Buffer.from(r.data,'base64'));};
  await screenshot('desktop.png');
  for(const width of [390,320]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:true});
    await sleep(200);
    assert(await evaluate(`document.documentElement.scrollWidth <= window.innerWidth`),'Débordement horizontal à '+width+'px');
    if(width===390)await screenshot('mobile.png');
  }
  assert.deepEqual(errors,[]);
  console.log('CHROME_OK: saisie, accents, doublons, erreurs, tri, sauvegarde, règles, écrans 1440/390/320px, aucune erreur JavaScript.');
  await call('Browser.close');
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{if(socket)socket.close();chrome.kill();});
