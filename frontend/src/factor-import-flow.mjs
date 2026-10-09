const aliases = {
  period: ['period', 'period_end'],
  value: ['value'],
  available_at: ['available_at', 'publication_date', 'published'],
};

export function suggestFactorMapping(columns) {
  const result = {};
  for (const [field, names] of Object.entries(aliases)) {
    const matches = columns.filter(c => names.includes(String(c.label).trim().toLowerCase().replaceAll(' ', '_')));
    if (matches.length === 1) result[field] = matches[0].id;
  }
  return result;
}

export function factorMappingReady(mapping, columns) {
  const selected = Object.keys(aliases).map(key => mapping[key]);
  return selected.every(value => value && columns.some(c => c.id === value)) && new Set(selected).size === 3;
}

export function factorUnit(config) {
  const d=config.factor_details;
  if(d?.kind==='exchange_rate')return 'IRR per '+d.currency;
  if(d?.kind==='inflation')return d.measure==='cpi_index'?'CPI index (base '+d.base_year+' = 100)':
    ({monthly_change:'% monthly change',year_on_year:'% year-on-year change',annual_average:'% annual-average change'}[d.measure]||'');
  return config.unit||'';
}

export function factorTypeDefaults(kind) {
  if(kind==='exchange_rate')return {kind,currency:'USD',market:'',side:'',amount_unit:'',quote_quantity:1};
  if(kind==='inflation')return {kind,measure:'',base_year:''};
  return undefined;
}

export function factorSourceReady(config) {
  if(![config.name,config.geography,config.provider].every(v=>typeof v==='string'&&v.trim()))return false;
  const d=config.factor_details;
  if(!d)return !!config.unit?.trim();
  if(d.kind==='exchange_rate')return /^[A-Z]{3}$/.test(d.currency)&&!['IRR','IRT'].includes(d.currency)&&
    !!d.market&&!!d.side&&!!d.amount_unit&&Number(d.quote_quantity)>0&&Number(d.quote_quantity)<=1_000_000;
  return !!d.measure&&(d.measure!=='cpi_index'||/^\d{4}$/.test(d.base_year));
}
