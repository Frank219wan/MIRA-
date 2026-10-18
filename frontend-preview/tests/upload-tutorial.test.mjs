import test from 'node:test';
import assert from 'node:assert/strict';
import { apiConfig } from '../src/lib/config.ts';
import { saveTutorialInput, getRecipeDTO, getTutorial } from '../src/services/tutorial.ts';

test('uploaded tutorial sends upload id and never replaces failed recognition with demo', async () => {
  const storage = new Map();
  globalThis.sessionStorage = {getItem:k=>storage.get(k) ?? null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
  const originalFetch = globalThis.fetch;
  const originalConfig = {...apiConfig};
  try {
    apiConfig.demoMode = true;
    apiConfig.mockFallback = true;
    await saveTutorialInput({kind:'image',name:'my tutorial',uploadId:'abc.png'});
    globalThis.fetch = async (url, options) => {
      assert.ok(url.endsWith('/tutorials/parse-upload'));
      assert.deepEqual(JSON.parse(options.body), {upload_id:'abc.png',title:'my tutorial'});
      return new Response(JSON.stringify({error:{code:'vision_not_configured',message:'真实识别未配置'}}), {status:503});
    };
    await assert.rejects(getRecipeDTO(), /真实识别未配置/);
    await assert.rejects(getTutorial(), /真实识别未配置/);
  } finally {
    globalThis.fetch = originalFetch;
    Object.assign(apiConfig, originalConfig);
  }
});
