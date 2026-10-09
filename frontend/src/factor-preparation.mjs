export function preparedSelection(report, ids) {
  if (!ids.length || ids.length>8 || new Set(ids).size!==ids.length) throw Error('Choose one to eight sources.');
  const rows=ids.map(id=>report.recommendations.find(r=>r.snapshot_id===id));
  if(rows.some(r=>!r?.can_prepare))throw Error('Check the source coverage before preparing it.');
  const whatIf=rows.find(r=>r.what_if);
  return {
    factors:rows.map(r=>({id:r.snapshot_id,lag:String(r.lag_months),value:'',monthly:true,monthlyValues:{},timingAccepted:false,calendarAccepted:false})),
    method:whatIf?whatIf.method:'factor_test',
    seriesIds:report.series_ids||null,
    preparation:{context:report.context,review_token:report.review_token,snapshot_ids:[...ids],
      ...(report.profile?{profile_series_id:report.profile.series_id}:{})},
  };
}
