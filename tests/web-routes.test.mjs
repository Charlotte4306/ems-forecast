import test from 'node:test';
import assert from 'node:assert/strict';
import {screenPaths,screenFromLocation,screenUrl} from '../web/routes.mjs';
test('all screen paths are short English slugs and survive direct navigation',()=>{
  for(const [key,path] of Object.entries(screenPaths)){
    assert.match(path,/^\/[a-z]+(?:-[a-z]+)*$/);
    assert.equal(screenFromLocation(new URL('https://emsforecast.live'+path)),key);
    assert.equal(screenFromLocation(new URL('https://emsforecast.live'+path+'/')),key);
  }
});
test('legacy links migrate without losing forecast selections',()=>{
  const url=new URL('https://emsforecast.live/?profile=lstm_h24&day=2026-10-11#kehoach');
  assert.equal(screenFromLocation(url),'kehoach');
  assert.equal(screenUrl(screenFromLocation(url),url),'/fleet-plan?profile=lstm-h24&day=2026-10-11');
  assert.equal(screenUrl('chiphi',url),'/scenario-costs?profile=lstm-h24&day=2026-10-11');
});
