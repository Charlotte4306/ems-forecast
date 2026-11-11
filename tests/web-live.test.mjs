import test from 'node:test';
import assert from 'node:assert/strict';
import {validateLive} from '../web/live.mjs';
function fixture(){
  const rows=Array.from({length:168},(_,i)=>({time:new Date(Date.UTC(2026,10,11,0)+i*3600000).toISOString().slice(0,19),prediction:10}));
  return {schemaVersion:1,timezone:'America/Los_Angeles',target:'medic-dispatches',unit:'dispatches',timeField:'received_dttm',identityField:'rowid',generatedAt:'2026-11-11T18:00:00Z',rows,days:Array.from({length:7},(_,i)=>({date:rows[i*24].time.slice(0,10),prediction:240}))};
}
test('forward forecasts validate without invented actual observations',()=>{const value=fixture();assert.equal(validateLive(value),value);assert.ok(value.rows.every(row=>!Object.hasOwn(row,'actual')));});
test('invalid future snapshots fail instead of rendering misleading values',()=>{const duplicate=fixture();duplicate.rows[1].time=duplicate.rows[0].time;assert.throws(()=>validateLive(duplicate));const negative=fixture();negative.rows[0].prediction=-1;assert.throws(()=>validateLive(negative));});
test('call-count forecasts cannot be displayed as dispatch forecasts',()=>{const calls=fixture();calls.target='unique-medic-calls';calls.unit='calls';assert.throws(()=>validateLive(calls));const wrongClock=fixture();wrongClock.timeField='dispatch_dttm';assert.throws(()=>validateLive(wrongClock));});
