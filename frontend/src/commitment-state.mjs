export function commitmentPeriods(run){
  return [...new Set(Object.values(run?.series||{}).flatMap(series=>(series.forecast||[]).map(row=>row.timestamp)))].sort();
}
export function commitmentKey(row){return JSON.stringify([row.customer,row.sku,row.unit,row.period]);}
export function commitmentError(row,inputs,periods,index){
  if(!inputs.customers.some(c=>c.customer===row.customer&&c.sku===row.sku&&c.unit===row.unit))return 'Choose a customer and product.';
  if(!periods.includes(row.period))return 'Choose a forecast month.';
  if(String(row.quantity).trim()===''||!Number.isFinite(Number(row.quantity))||Number(row.quantity)<0)return 'Enter a quantity of zero or more.';
  if(!row.owner.trim())return 'Enter the person responsible.';
  if(row.reason.trim().length<3)return 'Explain the monthly commitment.';
  if(!/^\d{4}-\d{2}-\d{2}$/.test(row.valid_until)||row.valid_until<inputs.as_of)return 'Review expiry must be on or after the source date.';
  if(inputs.commitments.some((other,i)=>i!==index&&commitmentKey(other)===commitmentKey(row)))return 'This customer and product already have a commitment for this month.';
  return null;
}
