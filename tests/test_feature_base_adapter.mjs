import test from 'node:test';
import assert from 'node:assert/strict';
const {beforeToolCall, executeAction, register} = await import('../plugins/feature-base-guard/policy.mjs');
const contract={repo:'/fixture/repo',base:'a'.repeat(40),expectedCommits:1,allowedPaths:['owned.txt']};
const config={contracts:{task:contract}};
const event=(action='deliver',contractId='task')=>({toolName:'feature_base_action',params:{action,contractId}});
const valid=async()=>({valid:true,commits:1,head:'b'.repeat(40)});
const failed=async()=>{throw new Error('commit count 11 != expected 1');};
test('unrelated tools are outside supported route',async()=>assert.equal(await beforeToolCall({toolName:'read',params:{}},config,failed),undefined));
test('valid configured delivery allowed',async()=>assert.equal(await beforeToolCall(event(),config,valid),undefined));
test('invalid range is terminal veto',async()=>assert.equal((await beforeToolCall(event(),config,failed)).block,true));
test('unknown contract fails closed',async()=>assert.equal((await beforeToolCall(event('deliver','absent'),config,valid)).block,true));
test('caller cannot override base or paths',async()=>assert.equal((await beforeToolCall({...event(),params:{...event().params,base:'other'}},config,valid)).block,true));
test('malformed configuration fails closed',async()=>assert.equal((await beforeToolCall(event(),{contracts:{task:{...contract,expectedCommits:-1}}},valid)).block,true));
test('unsupported action fails closed',async()=>assert.equal((await beforeToolCall(event('push'),config,valid)).block,true));
test('verifier receives configured base/scope and correct mode',async()=>{let observed;await beforeToolCall(event('start'),config,async(...args)=>{observed=args;return {valid:true};});assert.deepEqual(observed,[contract,'start',0]);});
test('commit requires message and terminal stage check',async()=>{const e=event('commit');assert.equal((await beforeToolCall(e,config,valid)).block,true);e.params.message='fix: guarded change';let observed;assert.equal(await beforeToolCall(e,config,async(...a)=>{observed=a;return {valid:true};}),undefined);assert.deepEqual(observed,[contract,'stage',0]);});
test('helper invalid result fails closed',async()=>assert.equal((await beforeToolCall(event(),config,async()=>({valid:false}))).block,true));
test('execution repeats guard before mutation',async()=>{let mutation=false;await assert.rejects(()=>executeAction(event('commit').params,config,failed,async()=>{mutation=true;}));assert.equal(mutation,false);});
test('guarded commit uses argv and rechecks delivery',async()=>{const p={action:'commit',contractId:'task',message:'fix: guarded change'};let args;let checks=[];await executeAction(p,config,async(c,m,n)=>{checks.push([m,n]);return {valid:true};},async a=>{args=a;});assert.deepEqual(args,['-C',contract.repo,'commit','-m',p.message]);assert.deepEqual(checks,[['stage',0],['deliver',1]]);});
test('native registration installs hook and constrained tool',()=>{let hook,tool;register({pluginConfig:config,on:(...a)=>{hook=a;},registerTool:t=>{tool=t;}});assert.equal(hook[0],'before_tool_call');assert.equal(tool.name,'feature_base_action');assert.equal(tool.parameters.additionalProperties,false);});

test('real helper allows corrected range and reports old eleven commits',async()=>{
  const {mkdtemp,writeFile,rm}=await import('node:fs/promises');
  const {tmpdir}=await import('node:os');
  const {join}=await import('node:path');
  const {execFileSync}=await import('node:child_process');
  const dir=await mkdtemp(join(tmpdir(),'feature-base-adapter-'));
  const git=(...a)=>execFileSync('git',['-C',dir,...a],{encoding:'utf8'}).trim();
  try{
    git('init','-q');git('config','core.hooksPath','/dev/null');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');
    await writeFile(join(dir,'owned.txt'),'base');git('add','owned.txt');git('commit','-qm','chore: fixture base');
    const base=git('rev-parse','HEAD');const c={contracts:{task:{repo:dir,base,expectedCommits:1,allowedPaths:['owned.txt']}}};
    assert.equal(await beforeToolCall(event('start'),c),undefined);
    await writeFile(join(dir,'owned.txt'),'feature');git('add','owned.txt');
    const result=await executeAction({contractId:'task',action:'commit',message:'fix: fixture guarded commit'},c);
    assert.equal(result.commits,1);assert.equal(await beforeToolCall(event(),c),undefined);
    for(let n=2;n<=11;n++){await writeFile(join(dir,'owned.txt'),String(n));git('add','owned.txt');git('commit','-qm','fix: fixture additional');}
    const blocked=await beforeToolCall(event(),c);assert.equal(blocked.block,true);assert.match(blocked.blockReason,/commit count 11/);
  }finally{await rm(dir,{recursive:true,force:true});}
});
