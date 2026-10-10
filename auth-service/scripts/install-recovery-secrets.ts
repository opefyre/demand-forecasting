import {readFile,lstat} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
try {
  const configPath=process.argv[2];if(!configPath)throw Error();
  const config=JSON.parse(await readFile(configPath,'utf8'));
  if(config.name!=='demandlab-forecast-recovery-rehearsal'||config.account_id!=='b53df72f41f5135daf312100e73ff6a1'||config.workers_dev!==false||config.preview_urls!==false||config.routes.length||config.vars.PRIVATE_ACCESS!=='closed')throw Error();
  const get=async(name:string)=>{const path=fileURLToPath(new URL('../../secrets/'+name,import.meta.url)),info=await lstat(path);
    if(!info.isFile()||info.isSymbolicLink()||(info.mode&0o077)||info.size>256)throw Error();const value=(await readFile(path,'utf8')).trim();if(!/^[a-f0-9]{64}$/.test(value))throw Error();return value;};
  const values={AUTH_RECOVERY_KEY:await get('forecast-auth-secret.txt'),VAULT_RECOVERY_KEY:await get('forecast-company-vault-key.txt')};
  // Pinned official CLI, stdin only, never log credentials or child error output.
  const child=spawn('npx',['--yes','wrangler@4.149.0','secret','bulk','--config',configPath],
    {stdio:['pipe','ignore','ignore'],env:{...process.env,WRANGLER_SEND_METRICS:'false'}});
  child.stdin.end(JSON.stringify(values));
  await new Promise<void>((resolve,reject)=>{child.once('error',reject);child.once('close',code=>code===0?resolve():reject(Error()));});
  console.log('Private rehearsal decryption secrets installed; values not displayed.');
}catch{console.error('Rehearsal secret setup failed without displaying credentials.');process.exitCode=1;}
