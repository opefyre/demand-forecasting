export function comparisonRows(rows, customer='', sku='') {
  const groups=new Map();
  for(const row of rows.filter(r=>(!customer||r.customer===customer)&&(!sku||r.sku===sku))) {
    const key=JSON.stringify([row.period,row.unit]);
    if(!groups.has(key))groups.set(key,{period:row.period,unit:row.unit,booked:0,fulfilled:0,before_remaining:0,after_remaining:0,before_total:0,after_total:0,difference:0});
    const total=groups.get(key);
    for(const field of ['booked','fulfilled','before_remaining','after_remaining','before_total','after_total','difference'])
      total[field]=total[field]===null||row[field]==null?null:total[field]+row[field];
  }
  return [...groups.values()].sort((a,b)=>a.period.localeCompare(b.period)||a.unit.localeCompare(b.unit));
}
