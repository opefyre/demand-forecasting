// Editing a saved version never edits the original or carries its approval forward.
export function orderRevision(saved) {
  return {
    base_snapshot_id: saved.id,
    inputs: {...structuredClone(saved.inputs), reviewed: false, note: ''},
  };
}

// Freshness is decided by the server, not the browser's clock.
export function orderReviewMessage(outlook,translate,canEdit=true) {
  if (!outlook || outlook.fresh) return '';
  if(translate&&!canEdit)return translate('A planner must review orders and their dates before export. Last review deadline: {{date}}.',{date:outlook.valid_until});
  if(translate)return translate('Review orders and their dates before exporting. Use “Review orders” above. Last review deadline: {{date}}.',{date:outlook.valid_until});
  return `Review the current order book and its dates to unlock demand totals and exports. Last review deadline: ${outlook.valid_until}.`;
}
