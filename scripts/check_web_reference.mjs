// Optional DOM QA: node scripts/check_web_reference.mjs <path-to-jsdom-api> [query]
// Uses a test-only jsdom installation; no browser or ML dependency in production.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

if(!process.argv[2])throw Error('Provide the path to jsdom/lib/api.js from a temporary test installation.');
const {JSDOM}=await import(pathToFileURL(path.resolve(process.argv[2])));
const dom=new JSDOM(fs.readFileSync('web/index.html','utf8'),{url:'http://127.0.0.1:8501/'+(process.argv[3]||'')});
Object.assign(globalThis,{window:dom.window,document:dom.window.document,location:dom.window.location,history:dom.window.history,localStorage:dom.window.localStorage,requestAnimationFrame:()=>0});
window.matchMedia=()=>({matches:false});window.scrollTo=()=>{};
globalThis.fetch=async url=>{
  const file=url==='/api/live-forecast'?'outputs/live/forecast.json':'outputs/web/dataset.json';
  return {ok:fs.existsSync(file),json:async()=>JSON.parse(fs.readFileSync(file,'utf8'))};
};
await import(pathToFileURL(path.resolve('web/app.mjs')));
for(let i=0;i<80&&!document.body.classList.contains('data-ready');i++)await new Promise(r=>setTimeout(r,25));
assert.ok(document.body.classList.contains('data-ready'),document.querySelector('.data-loading').textContent);
if(location.pathname==='/daily-forecast')assert.ok(document.querySelector('#screen-daily.active'));
if(fs.existsSync('outputs/live/forecast.json')){
  assert.equal(document.querySelectorAll('.live-day').length,7);
  assert.equal(document.querySelectorAll('.live-bar').length,24);
  document.querySelectorAll('.live-day')[6].click();
  assert.equal(document.querySelector('.live-day[aria-pressed=true]').dataset.day,JSON.parse(fs.readFileSync('outputs/live/forecast.json','utf8')).days[6].date);
}
assert.equal(document.querySelectorAll('.hm-cell').length,168);
assert.equal(document.querySelectorAll('.blob').length,5);
assert.equal(document.querySelectorAll('#screens > .page').length,8);
const navigationOrder=[...document.querySelectorAll('.nav button[data-screen]')].map(button=>button.dataset.screen);
assert.deepEqual(navigationOrder,['tongquan','dubao','kehoach','chiphi','danhgia','daily','lichsu','caidat']);
navigationOrder.forEach((key,index)=>{
  const expected=String(index+1).padStart(2,'0');
  assert.equal(document.querySelector('#screen-'+key+' .intro').dataset.chapter,expected);
  assert.equal(document.querySelectorAll('.zzz-rail button')[index].textContent,expected);
});
assert.equal(document.querySelectorAll('.ops-flow button').length,4);
assert.equal(document.querySelectorAll('#screen-tongquan .kpi').length,3);
assert.ok(document.querySelector('#screen-tongquan .ops-details'));
assert.ok(!document.querySelector('#screen-chiphi').textContent.includes('NaN'));
const expectedRows=window.EMS.forecast.length;
if(location.search.includes('day=2026-10-11')){
  assert.ok(document.querySelector('#screen-kehoach').textContent.includes('Chưa đủ ca'));
  assert.ok(document.querySelector('#screen-chiphi').textContent.includes('Chưa có ca hoàn chỉnh'));
}
assert.ok(document.querySelectorAll('svg.chart path').length>=6);
assert.equal(document.querySelectorAll('#screen-dubao .fc-grid:not(.head)').length,window.EMS.forecast.length);
assert.ok(!document.querySelector('#screen-danhgia').textContent.includes('168 giờ'));
assert.ok(!document.querySelector('#hist-table').textContent.includes('C-005480'));
const originalSearch=location.search;
for(const button of document.querySelectorAll('.nav button')){
  button.click();assert.ok(document.querySelector('#screen-'+button.dataset.screen).classList.contains('active'));
}
document.querySelector('.ops-flow button[data-destination="kehoach"]').click();
assert.ok(document.querySelector('#screen-kehoach').classList.contains('active'));
assert.equal(document.querySelector('.ops-flow [aria-current="step"]').dataset.destination,'kehoach');
assert.equal(location.search,originalSearch);
assert.equal(window.EMS.forecast.length,expectedRows);
assert.equal(document.querySelectorAll('.ops-press-dot').length,5);
await new Promise(resolve=>setTimeout(resolve,550));
assert.equal(document.querySelectorAll('.ops-press-dot').length,0);
document.querySelector('#motion-switch').click();document.querySelector('#btn-set-save').click();
assert.equal(JSON.parse(localStorage.getItem('emsforecast.reference-preferences')).motion,true);
document.querySelector('.ops-flow button[data-destination="kehoach"]').click();
assert.equal(document.querySelectorAll('.ops-press-dot').length,0);
console.log('DOM binding passed:',process.argv[3]||'default','forecast hours:',window.EMS.forecast.length,'168 heatmap cells, 7 screens, navigation, settings');
dom.window.close();
