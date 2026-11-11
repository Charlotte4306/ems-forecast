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
globalThis.fetch=async()=>({ok:true,json:async()=>JSON.parse(fs.readFileSync('outputs/web/dataset.json','utf8'))});
await import(pathToFileURL(path.resolve('web/app.mjs')));
for(let i=0;i<80&&!document.body.classList.contains('data-ready');i++)await new Promise(r=>setTimeout(r,25));
assert.ok(document.body.classList.contains('data-ready'),document.querySelector('.data-loading').textContent);
assert.equal(document.querySelectorAll('.hm-cell').length,168);
assert.equal(document.querySelectorAll('.blob').length,5);
assert.equal(document.querySelectorAll('#screens > .page').length,7);
assert.ok(document.querySelectorAll('svg.chart path').length>=6);
assert.equal(document.querySelectorAll('#screen-dubao .fc-grid:not(.head)').length,window.EMS.forecast.length);
assert.ok(!document.querySelector('#screen-danhgia').textContent.includes('168 giờ'));
assert.ok(!document.querySelector('#hist-table').textContent.includes('C-005480'));
for(const button of document.querySelectorAll('.nav button')){
  button.click();assert.ok(document.querySelector('#screen-'+button.dataset.screen).classList.contains('active'));
}
document.querySelector('#motion-switch').click();document.querySelector('#btn-set-save').click();
assert.equal(JSON.parse(localStorage.getItem('emsforecast.reference-preferences')).motion,true);
console.log('DOM binding passed:',process.argv[3]||'default','forecast hours:',window.EMS.forecast.length,'168 heatmap cells, 7 screens, navigation, settings');
dom.window.close();
