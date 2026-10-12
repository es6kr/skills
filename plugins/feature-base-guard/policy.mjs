import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {realpath} from 'node:fs/promises';
const runFile=promisify(execFile);
const helper=fileURLToPath(new URL('../../skills/git-repo/scripts/verify_feature_base.py',import.meta.url));
const TOOL='feature_base_action';
function request(params,config){
  if (!params || Object.keys(params).some(k=>!['action','contractId','message'].includes(k))) throw new Error('unsupported parameters');
  if (!['start','commit','deliver'].includes(params.action)) throw new Error('unsupported action');
  if (typeof params.contractId!=='string' || !Object.hasOwn(config?.contracts??{},params.contractId)) throw new Error('unknown contract');
  const c=config.contracts[params.contractId];
  if (!c || typeof c.repo!=='string' || !c.repo.startsWith('/') || !/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(c.base??'') || !Number.isSafeInteger(c.expectedCommits) || c.expectedCommits<0 || !Array.isArray(c.allowedPaths) || !c.allowedPaths.length || c.allowedPaths.some(p=>typeof p!=='string'||!p)) throw new Error('invalid pinned contract');
  if (params.action==='commit' && (c.expectedCommits<1 || typeof params.message!=='string' || !params.message.trim() || params.message.length>4096 || params.message.includes('\0'))) throw new Error('commit requires expectedCommits >= 1 and message');
  if (params.action!=='commit' && params.message!==undefined) throw new Error('message only supported for commit');
  const mode=params.action==='commit'?'stage':params.action;
  const count=params.action==='start'?0:params.action==='commit'?c.expectedCommits-1:c.expectedCommits;
  return {contract:c,mode,count};
}
export async function verifyContract(contract,mode,count){
  const repo=await realpath(contract.repo);
  const args=[helper,'--repo',repo,'--base',contract.base,'--mode',mode,'--expected-commits',String(count)];
  for(const p of contract.allowedPaths) args.push('--allow-path',p);
  let stdout;
  try{({stdout}=await runFile('python3',args,{timeout:30000,maxBuffer:1024*1024}));}
  catch(error){
    let reason='verifier process failed';
    try{const receipt=JSON.parse(error.stdout);if(typeof receipt.error==='string')reason=receipt.error;}catch{}
    throw new Error(reason);
  }
  const result=JSON.parse(stdout);
  if(result.valid!==true) throw new Error('verifier rejected contract');
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
