import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dayRows,score,validateProfiles,visibleSeries} from '../web/dashboard.mjs';
import {csv} from '../web/analysis.mjs';

const data=JSON.parse(readFileSync(new URL('../outputs/web/dataset.json',import.meta.url),'utf8'));

test('both horizons align on all 6796 real hours and reproduce reported MAE/MAPE',()=>{
  validateProfiles(data);
  const h1=data.profiles.prophet_h1,h24=data.profiles.prophet_h24;
  assert.equal(h1.rows.length,6796);assert.equal(h24.rows.length,6796);
  assert.deepEqual(h1.rows.map(r=>[r.time,r.actual]),h24.rows.map(r=>[r.time,r.actual]));
  assert.ok(Math.abs(score(h1.rows).mae-3.0338797608)<1e-9);
  assert.ok(Math.abs(score(h24.rows).mae-3.0500498751)<1e-9);
  assert.ok(Math.abs(score(h24.rows).mape-32.7488531768)<1e-9);
  assert.equal(score(h24.rows).percentageCount,6790);
});
test('zero demand contributes to MAE but is excluded from MAPE',()=>{
  assert.deepEqual(score([{actual:0,prediction:2},{actual:10,prediction:8}]),{mae:2,mape:20,count:2,percentageCount:1});
  assert.equal(score([]).mae,null);
  assert.equal(score([{actual:0,prediction:2}]).mape,null);
});
test('day-ahead replay opens all forecasts but no actuals at midnight',()=>{
  const rows=dayRows(data.profiles.prophet_h24,'2026-01-15');
  assert.equal(rows.length,24);
  assert.ok(visibleSeries(rows,24,0).every(r=>r.observed===null&&Number.isFinite(r.forecast)));
  assert.equal(visibleSeries(rows,24,8).filter(r=>r.observed!==null).length,8);
  const h1=visibleSeries(rows,1,8);
  assert.equal(h1.filter(r=>r.forecast!==null).length,9);
  assert.ok(h1.slice(8).every(r=>r.observed===null));
  assert.equal(rows[8].actual,data.profiles.prophet_h24.rows.find(r=>r.time===rows[8].time).actual);
});
test('partial final day stays partial and missing dates stay empty',()=>{
  assert.equal(dayRows(data.profiles.prophet_h24,'2026-10-11').length,4);
  assert.equal(dayRows(data.profiles.prophet_h24,'2027-01-01').length,0);
});
test('validation rejects gaps and observation cutoff after forecast issuance',()=>{
  const copy=structuredClone(data);copy.profiles.prophet_h24.rows[0].cutoff='2026-01-01T01:00:00';
  assert.throws(()=>validateProfiles(copy));
  const gap=structuredClone(data);gap.profiles.prophet_h1.rows.splice(3,1);assert.throws(()=>validateProfiles(gap));
});
test('CSV preserves UTF8 BOM and escapes delimiters and quotes',()=>{
  const result=csv([{time:'08:00',value:'a,"b"'}],[{key:'time',label:'Giờ'},{key:'value',label:'Giá trị'}]);
  assert.equal(result,'\uFEFF"Giờ","Giá trị"\r\n"08:00","a,""b"""');
});
