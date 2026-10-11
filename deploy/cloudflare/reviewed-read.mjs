import {companyRoute} from './company-api.mjs';

// Reuse only completed, immutable reads. Never cache actions, downloads, live
// provider calls or conversation bodies (their proposed actions can expire).
export function reviewedReadLifetime(path,who) {
  const entry=companyRoute('GET',path);
  if(!entry?.queued || entry.download || entry.network ||
    !entry.scopes.every(scope=>who.permissions?.includes(scope)))return 0;
  if(new URL(path,'https://company.invalid').pathname==='/ai/conversations') {
    // Restricted readers must re-evaluate approved-report access every time.
    // A company/service key must never gain private history via saved results.
    if(!['admin','planner'].includes(who.role) || who.key_kind==='company' ||
      /^(company-key:|service:)/.test(who.subject || '') ||
      !['reports:read','drafts:read','inputs:read'].every(scope=>who.permissions.includes(scope)))return 0;
    return 12*60*60*1000;
  }
  // Choice/review screens may contain freshness warnings. Keep this short and
  // leave preview/save verification authoritative; no approval token is reused.
  if(/^\/runs\/[a-zA-Z0-9_-]{1,128}\/factor-(links|profiles)$/.test(path))return 30*1000;
  return 0;
}

export function sameReadPrincipal(saved,current) {
  const fields=['company_id','issuer','subject','role','auth_kind','key_kind'];
  return fields.every(field=>saved[field]===current[field]) &&
    Array.isArray(saved.permissions) && Array.isArray(current.permissions) &&
    JSON.stringify([...new Set(saved.permissions)].sort())===JSON.stringify([...new Set(current.permissions)].sort());
}

export function reusableRead(row,path,who,revision,now=Date.now()) {
  const lifetime=reviewedReadLifetime(path,who);
  if(!lifetime || row.kind!=='api' || row.company!==who.company_id || row.state!=='succeeded' || row.api_status!==200 ||
    row.input_revision!==revision || !Number.isSafeInteger(row.completed_at) || row.completed_at>now || now-row.completed_at>=lifetime)return null;
  try {
    const request=JSON.parse(row.payload),grant=JSON.parse(row.grant_json),artifacts=JSON.parse(row.artifacts);
    const key=artifacts['api-response.json'];
    if(request.method!=='GET' || request.path!==path || !sameReadPrincipal(grant,who) ||
      typeof key!=='string' || key!==`companies/${who.company_id}/outputs/${row.id}/${row.attempt}/api-response.json` ||
      artifacts['api-download.bin'])return null;
    return key;
  }catch{return null;}
}
