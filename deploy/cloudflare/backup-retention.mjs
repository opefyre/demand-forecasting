import {validateRecovery,recoveredGrant} from './recovery-ledger.mjs';

// Expire ONLY redundant ledger history. Published archives and the latest ledger
// have no age limit: an idle company must remain recoverable after thirty days.
export const HISTORY_PREFIX='_ledger-history/';
export const HISTORY_DAYS=30;
export function backupCopy(snapshot) {
  // Recovery format is JSON; use the same serialization in Node and workerd.
  const value=JSON.parse(JSON.stringify(validateRecovery(snapshot,snapshot.company_id)));
  value.jobs=value.jobs.map(row=>({...row,grant_json:recoveredGrant(row.grant_json)}));
  return validateRecovery(value,value.company_id);
}
export async function persistBackup(bucket,snapshot) {
  const value=backupCopy(snapshot),bytes=new TextEncoder().encode(JSON.stringify(value));
  const latest='companies/'+value.company_id+'/recovery/latest.json';
  const history=HISTORY_PREFIX+value.company_id+'/'+value.captured_at+'-'+crypto.randomUUID()+'.json';
  const sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');
  const options={customMetadata:{sha256,company:value.company_id,revision:value.head.revision},httpMetadata:{contentType:'application/json'}};
  if(!await bucket.put(history,bytes,{...options,onlyIf:{etagDoesNotMatch:'*'}}))throw Error('Backup unavailable');
  if(!await bucket.put(latest,bytes,options))throw Error('Backup unavailable');
  return {verified:true,company_id:value.company_id,revision:value.head.revision,
    captured_at:value.captured_at,sha256,latest,history,history_days:HISTORY_DAYS};
}
