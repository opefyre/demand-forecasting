// Produce private offline identity/probe files. Credentials never reach stdout.
import {readFile,lstat,open} from 'node:fs/promises';
import {createHash,randomBytes,createCipheriv} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
const hash=(value:Buffer)=>createHash('sha256').update(value).digest('hex');
const company='wJgSr727WvzGlU4uMVSPzwA01j75gmr0',id='dr-20261010';
async function privateFile(path:string) {const info=await lstat(path);if(!info.isFile()||info.isSymbolicLink()||(info.mode&0o077)||info.size>64*1024*1024)throw Error();return readFile(path);}
async function save(path:string,data:string){const file=await open(path,'wx',0o600);try{await file.writeFile(data);}finally{await file.close();}}
try {
  const directory=process.argv[2],expected=process.argv[3];if(!directory||!/^[a-f0-9]{64}$/.test(expected||''))throw Error();
  const original=await privateFile(directory+'/identity.sql');if(hash(original)!==expected||/\b(?:ATTACH|DETACH)\b|load_extension\s*\(/i.test(original.toString()))throw Error();
  const db=new DatabaseSync(':memory:',{allowExtension:false});
  try {
    db.exec(original.toString());
    db.exec(`DELETE FROM demandlab_session_mfa; DELETE FROM demandlab_session_company; DELETE FROM "session"; DELETE FROM verification;
      UPDATE apikey SET enabled=0; UPDATE demandlab_key_bindings SET revoked=1;
      UPDATE invitation SET status='canceled' WHERE status='pending';
      UPDATE account SET accessToken=NULL,refreshToken=NULL,idToken=NULL,accessTokenExpiresAt=NULL,refreshTokenExpiresAt=NULL;`);
    const quote=(v:any)=>v===null?'NULL':typeof v==='number'?String(v):"'"+String(v).replaceAll("'","''")+"'";
    const tables=db.prepare("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").all();
    let sql='PRAGMA foreign_keys=OFF;\n';
    for(const table of tables){sql+=table.sql+';\n';for(const row of db.prepare('SELECT * FROM "'+String(table.name).replaceAll('"','""')+'"').all())
      sql+='INSERT INTO "'+table.name+'" ('+Object.keys(row).map(name=>'"'+name+'"').join(',')+') VALUES ('+Object.values(row).map(quote).join(',')+');\n';}
    for(const index of db.prepare("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").all())sql+=index.sql+';\n';
    await save(directory+'/identity-rehearsal.sql',sql);
  } finally {db.close();}
  const vault=(await privateFile(new URL('../../secrets/forecast-company-vault-key.txt',import.meta.url).pathname)).toString().trim();
  if(!/^[a-f0-9]{64}$/.test(vault))throw Error();
  const clear=randomBytes(32),nonce=randomBytes(12),cipher=createCipheriv('aes-256-gcm',Buffer.from(vault,'hex'),nonce);
  cipher.setAAD(Buffer.from(JSON.stringify([company,'recovery-probe',id])));
  const sealed=Buffer.concat([nonce,cipher.update(clear),cipher.final(),cipher.getAuthTag()]);
  await save(directory+'/vault-probe.json',JSON.stringify({sealed:sealed.toString('base64'),expected_sha256:hash(clear)}));
  console.log('Private identity restore and company-bound encryption probe prepared. No credentials displayed.');
}catch{console.error('Private preparation failed; no live data changed.');process.exitCode=1;}
