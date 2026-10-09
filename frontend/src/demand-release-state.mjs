export const releaseModes=[['remaining_forecast','Yes — exclude orders'],['combined_demand','No — include orders']];
export function visibleReleases(items,includeSamples=false){
  return items.filter(r=>includeSamples||!r.demo_only);
}
export function releaseLabel(r){
  if(r.superseded)return 'Replaced';
  if(r.blocked)return 'Inputs need review';
  if(r.state==='approved')return r.demo_only?'Demo approved':'Approved';
  return 'Awaiting review';
}
export function releaseDownload(r,kind){
  if(!r?.can_export||!['csv','xlsx','json'].includes(kind))return null;
  return '/api/sales/releases/'+encodeURIComponent(r.id)+'/export?kind='+kind;
}
export function releaseReady(receiver,report,contract){
  return !!receiver.trim()&&!!report&&report.contract.receiver===receiver.trim()&&report.contract.mode===contract;
}
