import assert from 'node:assert/strict';
import fs from 'node:fs';
import {dailyPlan} from '../web/operations.mjs';
import {score,validateProfiles} from '../web/dashboard.mjs';

const data=validateProfiles(JSON.parse(fs.readFileSync('outputs/web/dataset.json','utf8')));
const keys=['prophet_h24','sarimax_h24','lstm_h24'];
const names={prophet_h24:'Prophet 24h',sarimax_h24:'SARIMAX 24h',lstm_h24:'LSTM 24h block'};
const expected={prophet_h24:[3.05004987505655,32.7488531767985],sarimax_h24:[3.012486314823568,33.252348177635],lstm_h24:[3.00899118,33.96859216]};
const reference=data.profiles.prophet_h24.rows;
const days=[...new Set(reference.map(r=>r.time.slice(0,10)))];
for(const key of keys){
  const p=data.profiles[key];assert.equal(p.rows.length,6796);
  assert.deepEqual(p.rows.map(r=>[r.time,r.actual]),reference.map(r=>[r.time,r.actual]));
  const metrics=score(p.rows);assert.ok(Math.abs(metrics.mae-expected[key][0])<1e-5);assert.ok(Math.abs(metrics.mape-expected[key][1])<1e-4);
  for(const [policy,label] of [['mean','Trung bình'],['p90','P90']])for(const shift of ['shift8','shift12'])for(const ratio of [2,3,5,10,20]){
    const plans=days.map(day=>dailyPlan(data.operations,key,day,policy,shift,ratio));
    assert.equal(plans.reduce((s,r)=>s+r.hours,0),6792);
    assert.equal(plans.reduce((s,r)=>s+r.excluded,0),4);
    const report=data.operations.reports.evaluation_shifts.find(r=>r['Nguồn dự báo']===names[key]&&r['Kế hoạch theo']===label&&Number(r['ρ_max'])===0.8&&r['Kiểu ca'].startsWith(shift==='shift8'?'3 ca':'2 ca'));
    assert.ok(report);
    for(const [field,column] of [['cost',`Chi phí (thiếu = ${ratio}× thừa)`],['shortage','Xe-giờ thiếu'],['excess','Xe-giờ thừa']]){
      assert.ok(Math.abs(plans.reduce((s,r)=>s+r[field],0)-Number(report[column]))<1e-6,`${key}/${policy}/${shift}/${ratio}/${field}`);
    }
    const tail=dailyPlan(data.operations,key,'2026-10-11',policy,shift,ratio);
    assert.equal(tail.hours,0);assert.equal(tail.excluded,4);assert.equal(tail.peak,null);
  }
}
assert.equal(dailyPlan(null,'prophet_h24','2026-09-29'),null);
assert.equal(dailyPlan(data.operations,'prophet_h24','2026-09-29','mean','shift8',4),null);
console.log('PASS: all 3 H24 metrics; all 60 policy/shift/cost combinations match Python reports; 6792 complete hours and incomplete tail.');
