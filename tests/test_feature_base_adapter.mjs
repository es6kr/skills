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
test('windows absolute worktree path allowed in contract',async()=>assert.equal(await beforeToolCall(event(),{contracts:{task:{...contract,repo:'C:\\\\Users\\\\runneradmin\\\\repo'}}},valid),undefined));
test('relative worktree path fails closed in contract',async()=>assert.equal((await beforeToolCall(event(),{contracts:{task:{...contract,repo:'relative/path'}}},valid)).block,true));
test('verifier receives configured base/scope and correct mode',async()=>{let observed;await beforeToolCall(event('start'),config,async(...args)=>{observed=args;return {valid:true};});assert.deepEqual(observed,[contract,'start',0]);});
test('commit requires message and terminal stage check',async()=>{const e=event('commit');assert.equal((await beforeToolCall(e,config,valid)).block,true);e.params.message='fix: guarded change';let observed;assert.equal(await beforeToolCall(e,config,async(...a)=>{observed=a;return {valid:true};}),undefined);assert.deepEqual(observed,[contract,'stage',0]);});
test('helper invalid result fails closed',async()=>assert.equal((await beforeToolCall(event(),config,async()=>({valid:false}))).block,true));
test('execution repeats guard before mutation',async()=>{let mutation=false;await assert.rejects(()=>executeAction(event('commit').params,config,failed,async()=>{mutation=true;}));assert.equal(mutation,false);});
test('guarded commit uses argv and rechecks delivery',async()=>{const p={action:'commit',contractId:'task',message:'fix: guarded change'};let args;let checks=[];await executeAction(p,config,async(c,m,n)=>{checks.push([m,n]);return {valid:true};},async a=>{args=a;});assert.deepEqual(args,['-C',contract.repo,'commit','-m',p.message]);assert.deepEqual(checks,[['stage',0],['deliver',1]]);});
test('native registration installs hook and constrained tool',()=>{let hook,tool;register({pluginConfig:config,on:(...a)=>{hook=a;},registerTool:t=>{tool=t;}});assert.equal(hook[0],'before_tool_call');assert.equal(tool.name,'feature_base_action');assert.equal(tool.parameters.additionalProperties,false);});

test('packaged helper is byte-identical to canonical helper',async()=>{
  const {readFile}=await import('node:fs/promises');
  assert.deepEqual(await readFile(new URL('../plugins/feature-base-guard/resources/verify_feature_base.py',import.meta.url)),await readFile(new URL('../skills/git-repo/scripts/verify_feature_base.py',import.meta.url)));
});

test('captured package alone allows delivery and preserves terminal range veto',async()=>{
  const {mkdtemp,mkdir,writeFile,cp,rm}=await import('node:fs/promises');
  const {tmpdir}=await import('node:os');const {join}=await import('node:path');
  const {pathToFileURL}=await import('node:url');const {execFileSync}=await import('node:child_process');
  const dir=await mkdtemp(join(tmpdir(),'feature-base-captured-'));const repo=join(dir,'repo');
  try{
    await mkdir(repo);const git=(...a)=>execFileSync('git',['-C',repo,...a],{encoding:'utf8'}).trim();
    git('init','-q');git('config','core.hooksPath','/dev/null');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');
    await writeFile(join(repo,'owned.txt'),'base');git('add','owned.txt');git('commit','-qm','chore: fixture base');const base=git('rev-parse','HEAD');
    await writeFile(join(repo,'owned.txt'),'feature');git('add','owned.txt');git('commit','-qm','fix: fixture feature');
    const cache=join(dir,'captured-package');await cp(new URL('../plugins/feature-base-guard/',import.meta.url),cache,{recursive:true});
    const loaded=await import(pathToFileURL(join(cache,'policy.mjs')).href);let hook,tool;
    // An original root is deliberately absent and irrelevant to this captured package.
    loaded.register({rootDir:join(dir,'nonexistent-source'),pluginConfig:{contracts:{task:{repo,base,expectedCommits:1,allowedPaths:['owned.txt']}}},on:(_name,fn)=>{hook=fn;},registerTool:t=>{tool=t;}});
    assert.equal(await hook(event()),undefined);
    assert.equal((await tool.execute('fixture',event().params)).details.head,git('rev-parse','HEAD'));
    for(let n=2;n<=11;n++){await writeFile(join(repo,'owned.txt'),String(n));git('add','owned.txt');git('commit','-qm','fix: fixture additional');}
    assert.deepEqual(await hook(event()),{block:true,blockReason:'Feature base guard: commit count 11 != expected 1'});
    await assert.rejects(()=>tool.execute('fixture',event().params),/commit count 11 != expected 1/);
  }finally{await rm(dir,{recursive:true,force:true});}
});

test('process failures expose only bounded categories, never stderr or receipt secrets',async()=>{
  const {verifyContract}=await import('../plugins/feature-base-guard/policy.mjs');
  const {mkdtemp,writeFile,rm}=await import('node:fs/promises');
  const {tmpdir}=await import('node:os');const {join}=await import('node:path');
  const dir=await mkdtemp(join(tmpdir(),'feature-base-diag-'));
  try{
    const c={...contract,repo:dir};
    await assert.rejects(()=>verifyContract(c,'deliver',1,join(dir,'absent.py')), {message:'verifier process failed [missing-helper]'});
    const script=join(dir,'fixture.py');
    for(const [body,category] of [
      ['import sys; sys.stderr.write("SECRET_STDERR"); sys.exit(2)','process-failed'],
      ['print("SECRET_MALFORMED")','malformed-receipt'],
      ['print("null")','malformed-receipt'],
      ['print("[]")','malformed-receipt'],
      ['print(\' {"valid":"true"} \')','malformed-receipt'],
      ['print(\' {"valid":false,"error":"SECRET_RECEIPT"} \')','rejected-contract'],
      ['print("SECRET_STDOUT" * 100000)','output-limit'],
      ['import time; time.sleep(60)','timeout'],
      ['print(\' {"valid":false,"error":"git command failed: SECRET_RECEIPT"} \'); raise SystemExit(3)','rejected-contract'],
      ['print(\' {"valid":true} \'); raise SystemExit(3)','process-failed'],
    ]){
      await writeFile(script,body);
      await assert.rejects(()=>verifyContract(c,'deliver',1,script),{message:`verifier process failed [${category}]`});
    }
    const previous=process.env.PATH;
    try{process.env.PATH=dir;await assert.rejects(()=>verifyContract(c,'deliver',1,script),{message:'verifier process failed [missing-interpreter]'});}
    finally{process.env.PATH=previous;}
  }finally{await rm(dir,{recursive:true,force:true});}
});

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
