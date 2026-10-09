// Reuse reviewed column names, never silently substitute a different column.
export function suggestedSalesGrouping(columns) {
  const present = new Set(columns || []);
  const customer_col = present.has('customer') ? 'customer' : '';
  const sku_col = present.has('sku') ? 'sku' : '';
  const item_col = ['series_id', 'item_id', 'sku'].find(c => present.has(c)) || '';
  return {customer_col, sku_col, item_col,
    series_mode: customer_col && sku_col ? 'customer_product' : 'column'};
}

export function salesGroupingReady(settings) {
  return settings.series_mode !== 'customer_product' || Boolean(
    settings.customer_col && settings.sku_col && settings.customer_col !== settings.sku_col);
}

export function replacementMapping(settings, columns, role) {
  const present = new Set(columns || []);
  const keys =
    role === "history"
      ? [
          "date_col",
          "target_col",
          "item_col",
          "sku_col",
          "category_col",
          "customer_col",
          "production_line_col",
        ]
      : ["future_date_col", "future_item_col"];
  const mapping = Object.fromEntries(
    keys.map((key) => [key, present.has(settings[key]) ? settings[key] : ""]),
  );
  if (role === "history") {
    // Row corrections are bound to one file, never carried into its replacement.
    mapping.history_cell_corrections = [];
    mapping.history_corrections_sha256 = null;
    mapping.drivers = (settings.drivers || []).filter((column) =>
      present.has(column),
    );
    mapping.driver_roles = Object.fromEntries(
      Object.entries(settings.driver_roles || {}).filter(([column]) =>
        mapping.drivers.includes(column),
      ),
    );
  }
  return mapping;
}

export const importDraftKey = (id) =>
  `demandlab.importDraft${id ? `.${id}` : ""}`;

export function saveAttempt(previous, payload, newId) {
  const contents = JSON.stringify(payload);
  return previous?.contents === contents ? previous : { contents, id: newId() };
}

export function sameSavedInputs(initial, draft, defaults) {
  return Boolean(
    initial &&
    !initial.import_candidate_id &&
    draft.name === initial.name &&
    draft.classification === initial.classification &&
    JSON.stringify(draft.sources) === JSON.stringify(initial.sources) &&
    JSON.stringify({ ...defaults, ...draft.settings }) ===
      JSON.stringify({ ...defaults, ...initial.settings }),
  );
}
