import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {metrics,capacity,replay,blocks,validateDataset} from '../web/analysis.mjs';

const rows=[{time:'2026-01-02T00:00:00',actual:0,prophet:1,lstm:1,baseline:2},{time:'2026-01-02T01:00:00',actual:10,prophet:8,lstm:9,baseline:0}];

test('WAPE includes zero-target errors and is not MAPE',()=>{
  const m=metrics(rows,'prophet');assert.equal(m.mae,1.5);assert.equal(m.wape,30);
  assert.equal(metrics([{...rows[0],actual:0}],'prophet').wape,null);
  assert.equal(metrics([],'prophet').mae,null);
});
test('replay hides current actual and predictions after the cutoff',()=>{
  const value=replay(rows,0);assert.equal(value[0].observed,null);assert.equal(value[0].predictionVisible,true);
  assert.equal(value[1].predictionVisible,false);assert.equal(value[1].observed,null);
  assert.equal(replay(rows,1)[0].observed,0);assert.equal(rows[1].actual,10);
});
test('capacity depends on predictions and declared assumptions only',()=>{
  const settings={fleet:5,minutes:60,utilization:.5};
  const calculated=capacity(rows,'prophet',settings);
  assert.deepEqual(calculated.map(r=>r.required),[2,16]);assert.deepEqual(calculated.map(r=>r.shortfall),[0,11]);
  assert.deepEqual(capacity(rows.map(r=>({...r,actual:999})),'prophet',settings).map(r=>r.required),[2,16]);
  assert.throws(()=>capacity(rows,'prophet',{...settings,utilization:0}));
});
test('capacity blocks respect time gaps',()=>{
  const fixture=[{time:'2026-01-02T00:00:00',shortfall:2},{time:'2026-01-02T01:00:00',shortfall:4},{time:'2026-01-02T03:00:00',shortfall:1}];
  assert.equal(blocks(fixture).length,2);assert.equal(blocks(fixture)[0].hours,2);assert.equal(blocks(fixture)[0].peak,4);
});
test('the real exported dataset is aligned and reproduces model results',()=>{
  const data=validateDataset(JSON.parse(readFileSync(new URL('../outputs/web/dataset.json',import.meta.url),'utf8')));
  assert.equal(data.rows.length,6772);assert.ok(Math.abs(metrics(data.rows,'lstm').mae-2.9820)<.001);
  assert.ok(Math.abs(metrics(data.rows,'prophet').mae-3.0306)<.001);assert.equal(data.metadata.models.arima.available,false);
  assert.equal(data.metadata.uncertaintyAvailable,false);
});
test('dataset validation rejects broken times and non-finite predictions',()=>{
  const base={schemaVersion:1,metadata:{count:2},rows};assert.equal(validateDataset(base),base);
  assert.throws(()=>validateDataset({...base,rows:[rows[0],{...rows[1],time:rows[0].time}]}));
  assert.throws(()=>validateDataset({...base,rows:[rows[0],{...rows[1],prophet:NaN}]}));
});
