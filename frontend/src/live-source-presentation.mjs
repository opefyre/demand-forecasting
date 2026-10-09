// Built-in source captions are UI labels. Unknown/custom source names are data.
const captions={servix:'Iran exchange rate',iran_cpi:'Iran monthly price index',
  commodities:'Energy & materials',supply:'Global supply pressure',hormuz:'Hormuz ship traffic',
  inflation:'Iran inflation',industry:'Iran industry'};
export function sourceCaption(source,translate){
  return captions[source.id]?translate(captions[source.id]):source.name;
}
export function sourceRefreshState(row,now=Date.now()){
  const hasData=!!row.series.length;
  const working=['queued','refreshing'].includes(row.status);
  const cooling=!!row.cooldown_until&&new Date(row.cooldown_until).getTime()>now;
  const needsPermission=row.permission_required&&!row.permission_confirmed;
  const status=needsPermission?'Permission needed':working?'Fetching data…':row.status==='failed'?'Refresh failed':
    row.refresh_overdue?'Refresh overdue':row.data_behind?'Source data is behind':row.enabled?'Auto-refresh on':
    hasData?'Saved · auto-refresh off':row.credential_configured?'Ready':'Not connected';
  return {hasData,working,cooling,needsPermission,status};
}
