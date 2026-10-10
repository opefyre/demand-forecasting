import { randomBytes } from 'node:crypto';
import { readFile, lstat, mkdir, open } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

// Dedicated engine-only encryption secret. Never print it or copy demo secrets.
const configPath=fileURLToPath(new URL('../../deploy/cloudflare/engine.wrangler.jsonc',import.meta.url));
const secretPath=fileURLToPath(new URL('../../secrets/forecast-company-vault-key.txt',import.meta.url));
try {
  const config=JSON.parse(await readFile(configPath,'utf8'));
  if(config.name!=='demandlab-forecast-engine' || config.account_id!=='b53df72f41f5135daf312100e73ff6a1' ||
      config.workers_dev!==false || config.preview_urls!==false || config.routes.length || config.vars.PRIVATE_ACCESS!=='closed' ||
      config.r2_buckets.map((b:any)=>b.bucket_name).join(',')!=='demandlab-forecast-files,demandlab-forecast-backups')throw new Error();
  await mkdir(fileURLToPath(new URL('../../secrets/',import.meta.url)),{recursive:true,mode:0o700});
  try {
    const file=await open(secretPath,'wx',0o600);
    try {await file.writeFile(randomBytes(32).toString('hex')+'\n');await file.sync();}finally{await file.close();}
  } catch(error:any) {if(error.code!=='EEXIST')throw error;}
  const stat=await lstat(secretPath);
  if(!stat.isFile() || stat.isSymbolicLink() || (stat.mode&0o077))throw new Error();
  const key=(await readFile(secretPath,'utf8')).trim();
  if(!/^[a-f0-9]{64}$/.test(key))throw new Error();
  if(process.argv.includes('--install')) {
    const child=spawn('npx',['--yes','wrangler@4.149.0','secret','bulk','--config',configPath],{
      stdio:['pipe','ignore','ignore'],env:{...process.env,WRANGLER_SEND_METRICS:'false'}});
    child.stdin.end(JSON.stringify({COMPANY_VAULT_KEY:key}));
    await new Promise<void>((resolve,reject)=>{child.once('error',reject);child.once('close',code=>code===0?resolve():reject(new Error()));});
  }
  console.log(process.argv.includes('--install')?'Dedicated engine encryption secret installed privately.':'Dedicated engine encryption secret validated; not displayed.');
}catch{console.error('Engine secret setup failed. No credential value was displayed.');process.exitCode=1;}
