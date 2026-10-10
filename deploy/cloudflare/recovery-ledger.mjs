// Operator-only recovery format. No public route and no executable SQL in backups.
const COMPANY=/^[A-Za-z0-9_-]{1,128}$/;
const ID=/^[a-f0-9]{32}$/;
export const MAX_RECOVERY_BYTES=4*1024*1024;
export function validateRecovery(value,company) {
  if(!COMPANY.test(company)||!value||value.version!==1||value.company_id!==company||
    new TextEncoder().encode(JSON.stringify(value)).byteLength>MAX_RECOVERY_BYTES||!Number.isSafeInteger(value.captured_at)||
    !value.head||value.head.company!==company||!ID.test(value.head.revision))throw Error('Invalid recovery snapshot');
  for(const table of ['revisions','jobs','schedules'])if(!Array.isArray(value[table])||value[table].length>10000||
    value[table].some(row=>!row||row.company!==company))throw Error('Invalid recovery snapshot');
  const key=(path)=>typeof path==='string'&&path.startsWith('companies/'+company+'/')&&!path.split('/').includes('..');
  if(value.head.object_key!=='companies/'+company+'/revisions/'+value.head.revision+'.zip'||
    value.head.view_key&&!key(value.head.view_key)||!value.revisions.some(r=>r.id===value.head.revision&&r.object_key===value.head.object_key)||
    value.revisions.some(r=>!ID.test(r.id)||r.object_key!=='companies/'+company+'/revisions/'+r.id+'.zip'))throw Error('Invalid recovery references');
  for(const row of value.jobs) {
    if(!ID.test(row.id)||!['queued','running','succeeded','failed','cancelled','interrupted'].includes(row.state))throw Error('Invalid recovery job');
    const payload=JSON.parse(row.payload),grant=JSON.parse(row.grant_json);
    if(grant.company_id!==company||payload.body_key&&!key(payload.body_key))throw Error('Invalid recovery job');
    if(row.artifacts&&Object.values(JSON.parse(row.artifacts)).some(path=>!key(path)))throw Error('Invalid recovery artifacts');
  }
  return value;
}
export function recoveryObjects(value) {
  const refs=new Set(value.revisions.map(row=>row.object_key));
  if(value.head.view_key)refs.add(value.head.view_key);
  for(const row of value.jobs) {
    const payload=JSON.parse(row.payload);if(payload.body_key)refs.add(payload.body_key);
    if(row.artifacts)for(const path of Object.values(JSON.parse(row.artifacts)))refs.add(path);
  }
  return [...refs];
}
export function recoveredGrant(raw) {
  const grant=JSON.parse(raw),safe={auth_kind:'recovered'};
  for(const name of ['issuer','company_id','subject','role','permissions','required_scopes'])if(grant[name]!==undefined)safe[name]=grant[name];
  return JSON.stringify(safe);
}
