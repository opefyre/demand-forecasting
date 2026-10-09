export function planningBasis(run) {
  return run?.run_settings?.calendar_profile?.month_basis || 'gregorian';
}

export function planningMonth(value, basis='gregorian') {
  if (!value) return '';
  if (basis !== 'jalali') return String(value).slice(0,7);
  const parts = new Intl.DateTimeFormat('en-u-ca-persian-nu-latn',{
    year:'numeric',month:'2-digit',timeZone:'UTC',
  }).formatToParts(new Date(String(value).slice(0,10)+'T12:00:00Z'));
  const get = type => parts.find(p=>p.type===type)?.value || '';
  return `${get('year')}-${get('month')}`;
}
