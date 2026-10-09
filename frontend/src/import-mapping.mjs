export const mappingLabels = {date_col:'Sales date',target_col:'Sales quantity',item_col:'Customer–SKU series',customer_col:'Customer',sku_col:'SKU',future_date_col:'Factor date',future_item_col:'Factor series'};

export function applyMappingSuggestion(settings, sources, diff) {
  const next = {...settings}, seen = new Set();
  for (const row of diff) {
    const role = row.field.startsWith('future_') ? 'future' : 'history';
    if (!Object.hasOwn(mappingLabels,row.field) || seen.has(row.field) ||
        (settings[row.field] || null) !== (row.before || null) ||
        !sources[role]?.preview?.columns?.includes(row.after)) {
      throw new Error('Inputs changed. Request new suggestions.');
    }
    seen.add(row.field);
    next[row.field] = row.after;
  }
  return next;
}
