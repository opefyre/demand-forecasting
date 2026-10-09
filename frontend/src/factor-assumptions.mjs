export function futureAssumptions(monthly, value, values) {
  const number = raw => {
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) throw new Error('Enter a number for each assumption, or leave it blank.');
    return parsed;
  };
  if (!monthly) return {future_value:value.trim()==='' ? null : number(value)};
  return {future_value:null, future_values:Object.fromEntries(
    Object.entries(values).filter(([,v])=>v.trim()!=='').map(([period,v])=>[period,number(v)])
  )};
}
