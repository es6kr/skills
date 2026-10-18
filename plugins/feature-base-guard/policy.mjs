import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {realpath,access} from 'node:fs/promises';
import {posix,win32} from 'node:path';
const runFile=promisify(execFile);
const helper=fileURLToPath(new URL('./resources/verify_feature_base.py',import.meta.url));
const TOOL='feature_base_action';
function request(params,config){
  if (!params || Object.keys(params).some(k=>!['action','contractId','message'].includes(k))) throw new Error('unsupported parameters');
  if (!['start','commit','deliver'].includes(params.action)) throw new Error('unsupported action');
  if (typeof params.contractId!=='string' || !Object.hasOwn(config?.contracts??{},params.contractId)) throw new Error('unknown contract');
  const c=config.contracts[params.contractId];
  const isAbs=typeof c?.repo==='string' && (posix.isAbsolute(c.repo) || win32.isAbsolute(c.repo));
  if (!c || !isAbs || !/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(c.base??'') || !Number.isSafeInteger(c.expectedCommits) || c.expectedCommits<0 || !Array.isArray(c.allowedPaths) || !c.allowedPaths.length || c.allowedPaths.some(p=>typeof p!=='string'||!p)) throw new Error('invalid pinned contract');
  if (params.action==='commit' && (c.expectedCommits<1 || typeof params.message!=='string' || !params.message.trim() || params.message.length>4096 || params.message.includes('\0'))) throw new Error('commit requires expectedCommits >= 1 and message');
  if (params.action!=='commit' && params.message!==undefined) throw new Error('message only supported for commit');
  const mode=params.action==='commit'?'stage':params.action;
  const count=params.action==='start'?0:params.action==='commit'?c.expectedCommits-1:c.expectedCommits;
  return {contract:c,mode,count};
}
function failure(category){return new Error(`verifier process failed [${category}]`);}
function rejection(receipt){
  // The helper can embed Git stderr and paths in its error field. Never relay
  // arbitrary subprocess text; retain only bounded, known semantic receipts.
  if(/^commit count \d{1,16} != expected \d{1,16}$/.test(receipt.error??''))return new Error(receipt.error);
  const safe=['clean worktree required','in-progress git operation','unmerged index',
    'feature range must be linear, not contain merge commits',
    'single feature commit must be a direct child of base','start HEAD must equal explicit base'];
  if(safe.includes(receipt.error))return new Error(receipt.error);
  return failure('rejected-contract');
}
export async function verifyContract(contract,mode,count,helperPath=helper){
  let repo;
  try{repo=await realpath(contract.repo);}catch{throw failure('invalid-repo');}
  try{await access(helperPath);}catch(error){throw failure(error.code==='ENOENT'?'missing-helper':'helper-unavailable');}
  const args=[helperPath,'--repo',repo,'--base',contract.base,'--mode',mode,'--expected-commits',String(count)];
  for(const p of contract.allowedPaths) args.push('--allow-path',p);
  let stdout;
  try{({stdout}=await runFile('python3',args,{timeout:30000,maxBuffer:1024*1024}));}
  catch(error){
    if(error.code==='ENOENT')throw failure('missing-interpreter');
    if(error.code==='ERR_CHILD_PROCESS_STDIO_MAXBUFFER')throw failure('output-limit');
    if(error.killed)throw failure('timeout');
    let receipt;
    try{receipt=JSON.parse(error.stdout);}catch{}
    if(receipt && receipt.valid===false)throw rejection(receipt);
    throw failure('process-failed');
  }
  let result;
  try{result=JSON.parse(stdout);}catch{throw failure('malformed-receipt');}
  if(!result || typeof result!=='object' || Array.isArray(result) || typeof result.valid!=='boolean')throw failure('malformed-receipt');
  if(result.valid!==true)throw rejection(result);
  return result;
}
async function checked(params,config,verify){
  const r=request(params,config);
  const result=await verify(r.contract,r.mode,r.count);
  if(result?.valid!==true) throw new Error('verifier did not return valid receipt');
  return {request:r,result};
}
export async function beforeToolCall(event,config,verify=verifyContract){
  if(event.toolName!==TOOL) return;
  try{await checked(event.params,config,verify);}
  catch(error){return {block:true,blockReason:'Feature base guard: '+error.message};}
}
export async function executeAction(params,config,verify=verifyContract,mutate=async args=>runFile('git',args,{timeout:120000,maxBuffer:1024*1024})){
  const {request:r,result}=await checked(params,config,verify);
  if(params.action!=='commit') return result;
  await mutate(['-C',r.contract.repo,'commit','-m',params.message]);
  // A post-commit failure is reported, never hidden or automatically reset.
  return await verify(r.contract,'deliver',r.contract.expectedCommits);
}
export function register(api){
  const config=structuredClone(api.pluginConfig??{});
  api.on('before_tool_call',event=>beforeToolCall(event,config),{matcher:[TOOL],priority:100});
  api.registerTool({name:TOOL,description:'Verify a pinned feature base or commit an already-staged, scope-limited change. No push/merge/staging.',parameters:{type:'object',additionalProperties:false,required:['contractId','action'],properties:{contractId:{type:'string'},action:{type:'string',enum:['start','commit','deliver']},message:{type:'string'}}},async execute(_id,params){const details=await executeAction(params,config);return {content:[{type:'text',text:JSON.stringify(details)}],details};}});
}
