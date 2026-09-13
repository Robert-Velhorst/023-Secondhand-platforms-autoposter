// Execute the shipped handlers, using a minimal DOM for deterministic state tests.
// Rendered Chromium checks remain a separate layer, not simulated by this DOM.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../public/app.js'), 'utf8');

async function fixture() {
  const nodes = new Map();
  function node(selector) {
    if (!nodes.has(selector)) {
      const classes = new Set(['#shell','#retrySessionButton'].includes(selector)?['hidden']:[]);
      const handlers = new Map();
      nodes.set(selector, {
        value:'', textContent:'', disabled:false, handlers, valid:true, dataset:{},
        classList:{add:c=>classes.add(c),remove:c=>classes.delete(c),contains:c=>classes.has(c),
          toggle(c,enabled){if(enabled)classes.add(c);else classes.delete(c);}},
        addEventListener:(event,handler)=>handlers.set(event,handler),
        setAttribute(){}, reportValidity(){return this.valid;},
      });
    }
    return nodes.get(selector);
  }
  const values = new Map();
  let reloads=0;
  const controls = ['#authEmail','#authPassword','#authName','#registerButton','#retrySessionButton','#logoutButton'].map(node);
  const context=vm.createContext({
    console, Error, AbortController, setTimeout,clearTimeout,FormData,URLSearchParams,URL,Set,Map,
    localStorage:{getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)},
    document:{querySelector:node,querySelectorAll:s=>s.startsWith('#authForm input')?controls:[],
      documentElement:{lang:'en'},body:node('body'),addEventListener(){}},
    window:{addEventListener(){},location:{reload(){reloads++;}}},
    fetch:async()=>({ok:true,status:200,headers:new Headers(),json:async()=>({status:'ok',supported_locales:[]})}),
  });
  vm.runInContext(source, context);
  await new Promise(resolve=>setImmediate(resolve));
  vm.runInContext('loadAll=async()=>{}; loadRequestedListing=async()=>{};', context);
  const app=vm.runInContext('({state,boot,submitAuth,runAuthAction,authApi})',context);
  return {...app,node,controls,values,context,reloads:()=>reloads,
    api(fn){context.mockApi=fn;vm.runInContext('api=mockApi;',context);},
    token(value='session-under-test'){app.state.token=value;values.set('autoposterToken',value);},
  };
}
const failure=status=>Object.assign(new Error('Synthetic request failure'),{status,retryable:status>=500});
const publicResponse=()=>({status:'ok',supported_locales:[]});

test('auth lock rejects overlap and releases controls after failure',async()=>{
  const f=await fixture();let release;let calls=0;
  const held=new Promise(resolve=>{release=resolve;});
  const pending=f.runAuthAction(async()=>{calls++;await held;throw failure(503);});
  assert.ok(f.controls.every(n=>n.disabled));
  await f.runAuthAction(async()=>{calls++;});
  assert.equal(calls,1);release();
  await assert.rejects(pending);
  assert.equal(f.state.authPending,false);
  assert.ok(f.controls.every(n=>!n.disabled));
});

test('invalid registration does not send an API request',async()=>{
  const f=await fixture();let calls=0;f.api(async()=>{calls++;});
  f.node('#authForm').valid=false;
  await f.node('#registerButton').handlers.get('click')();
  assert.equal(calls,0);assert.equal(f.state.authPending,false);
});

test('repeated sign-in and registration share one request',async()=>{
  const f=await fixture();let release;let calls=0;
  f.api(async()=>{calls++;await new Promise(resolve=>{release=resolve;});throw failure(401);});
  const first=f.submitAuth('login');await f.submitAuth('register');
  assert.equal(calls,1);release();await first;
  assert.equal(f.state.authPending,false);
  assert.equal(f.node('#authError').textContent,'Synthetic request failure');
});

test('transient session failure retains credentials and retry recovers',async()=>{
  const f=await fixture();f.token();let reject=true;
  f.api(async endpoint=>{
    if(endpoint!='/auth/me')return publicResponse();
    if(reject)throw failure(503);return {email:'fixture@example.com'};
  });
  await f.boot();
  assert.equal(f.values.get('autoposterToken'),'session-under-test');
  assert.equal(f.node('#retrySessionButton').classList.contains('hidden'),false);
  assert.equal(f.node('#shell').classList.contains('hidden'),true);
  reject=false;await f.node('#retrySessionButton').handlers.get('click')();
  assert.equal(f.node('#shell').classList.contains('hidden'),false);
  assert.equal(f.node('#retrySessionButton').classList.contains('hidden'),true);
  assert.equal(f.node('#authError').textContent,'');
});

for(const status of [401,403])test(`session ${status} clears invalid credentials`,async()=>{
  const f=await fixture();f.token();
  f.api(async endpoint=>{if(endpoint==='/auth/me')throw failure(status);return publicResponse();});
  await f.boot();assert.equal(f.state.token,null);assert.equal(f.values.has('autoposterToken'),false);
});

for(const reject of [false,true])test(`stale session ${reject?'failure':'success'} cannot replace newer state`,async()=>{
  const f=await fixture();f.token('old-session');let release;
  f.api(async endpoint=>{if(endpoint!='/auth/me')return publicResponse();
    await new Promise(resolve=>{release=resolve;});if(reject)throw failure(401);return {email:'old@example.com'};});
  const pending=f.boot();
  while(!release)await new Promise(resolve=>setImmediate(resolve));
  f.token('new-session');f.state.user={email:'new@example.com'};release();await pending;
  assert.equal(f.state.token,'new-session');assert.equal(f.state.user.email,'new@example.com');
});

test('auth timeout aborts the request and clears its timer',async()=>{
  const f=await fixture();let trigger;let cleared=false;
  f.context.setTimeout=fn=>{trigger=fn;return 42;};
  f.context.clearTimeout=id=>{assert.equal(id,42);cleared=true;};
  f.api(async(_,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('aborted')))));
  const pending=f.authApi('/auth/login');trigger();
  await assert.rejects(pending,/timed out/);assert.equal(cleared,true);
});

test('failed logout retains token and retry revokes before forgetting',async()=>{
  const f=await fixture();f.token();let reject=true;
  f.api(async()=>{if(reject)throw failure(503);return null;});
  const logout=f.node('#logoutButton').handlers.get('click');
  await logout();assert.equal(f.state.token,'session-under-test');assert.equal(f.reloads(),0);
  assert.equal(f.state.authPending,false);
  reject=false;await logout();assert.equal(f.state.token,null);assert.equal(f.values.has('autoposterToken'),false);
  assert.equal(f.reloads(),1);
});

test('dashboard loading does not lock logout or release a newer auth action',async()=>{
  const f=await fixture();f.token();let finishLoading;
  f.api(async endpoint=>endpoint==='/auth/me'?{email:'fixture@example.com'}:publicResponse());
  f.context.loadData=()=>new Promise(resolve=>{finishLoading=resolve;});
  vm.runInContext('loadAll=loadData;',f.context);
  const booting=f.runAuthAction(f.boot);
  while(!finishLoading)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.state.authPending,false,'Authenticated users must be able to sign out while dashboard reads wait');
  let finishNewAction;
  const newer=f.runAuthAction(()=>new Promise(resolve=>{finishNewAction=resolve;}));
  finishLoading();await booting;assert.equal(f.state.authPending,true);
  finishNewAction();await newer;assert.equal(f.state.authPending,false);
});
