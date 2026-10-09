export function changeReviewedInput(inputs, field, value) {
  return {...inputs, [field]:value, reviewed:field === 'reviewed' ? value : false};
}

export function requireSalesHeadings(preview) {
  if (!preview?.columns?.length) {
    throw new Error('No columns found on this heading row. Choose the row with your column names, then read headings again.');
  }
  return preview;
}

export function salesMappingReady(schema, config, heading) {
  if (!config) return true; // The saved rows are still in use.
  if (Number(heading) !== config.header_row) return false;
  const columns = new Set(config._preview?.columns.map(column => column.id) || []);
  return Object.entries(schema).every(([field, rule]) => {
    const selected = config.mapping?.[field];
    return selected ? columns.has(selected) : !rule.required;
  });
}
export function orderReviewReady(inputs) {
  return inputs?.reviewed===true && typeof inputs.note==='string' && inputs.note.trim().length>=3;
}
