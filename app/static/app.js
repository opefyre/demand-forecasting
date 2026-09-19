const $ = (id) => document.getElementById(id);
const state = {
  route: "today",
  workspace: null,
  plans: [],
  selectedPlan: null,
  result: null,
  activeItem: "__all__",
  historyFile: null,
  futureFile: null,
  operationsFile: null,
  operationsPreview: null,
  actualsFile: null,
  mappingSuggestions: null,
  historyPreview: null,
  futurePreview: null,
  selectedDrivers: new Set(),
  driverRoles: {},
  scenarios: [],
  savedViews: [],
  sourceClassification: "user_provided",
  loaderTimer: null,
  integrations: [],
  monitoring: null,
};

const routeNames = new Set(["today", "plans", "forecast", "methods", "supply", "scenarios", "assistant", "data", "performance", "admin"]);
const externalTokens = ["iran", "usd", "fx", "cpi", "price", "industrial", "pulp", "temperature", "weather", "energy", "logistics", "supplier", "lead_time", "market", "competitor"];
const metadataColumns = new Set(["date", "series_id", "sku", "product_name", "category", "customer", "site", "province", "warehouse", "production_line", "supplier", "demand_tonnes", "revenue_eur", "record_type", "source_sheet", "inventory_on_hand_tonnes", "safety_stock_tonnes", "monthly_capacity_tonnes", "unit_cost_irr", "service_level_target"]);
const preferredSignals = ["customer_orders_index", "open_orders_tonnes", "backlog_tonnes", "working_days", "usd_irr_synthetic", "iran_cpi_yoy_synthetic", "industrial_production_index_synthetic", "global_pulp_price_usd_synthetic", "energy_curtailment_hours_synthetic", "import_lead_time_days_synthetic", "supplier_fill_rate_synthetic", "event_code"];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
}
function humanize(value) {
  return String(value ?? "").replace(/_synthetic$/i, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function number(value, digits = 0) {
  const n = Number(value); return Number.isFinite(n) ? n.toLocaleString(undefined, {maximumFractionDigits: digits, minimumFractionDigits: digits}) : "—";
}
function compact(value) {
  const n = Number(value); return Number.isFinite(n) ? new Intl.NumberFormat(undefined, {notation:"compact", maximumFractionDigits:1}).format(n) : "—";
}
function pct(value, digits = 1) {
  const n = Number(value); return Number.isFinite(n) ? `${n.toFixed(digits)}%` : "—";
}
function formatDate(value, options = {}) {
  if (value == null || value === "") return "—";
  const date = new Date(value); if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en", {month:options.short ? "short" : "short", year:"numeric", day:options.day ? "numeric" : undefined}).format(date);
}
function inferRole(name) { return externalTokens.some((token) => String(name).toLowerCase().includes(token)) ? "external" : "internal"; }
function evidenceClass(value) { return ["strong", "moderate", "limited"].includes(value) ? value : "limited"; }
function emptyRow(columns, text) { return `<tr class="empty-row"><td colspan="${columns}">${escapeHtml(text)}</td></tr>`; }

function toast(type, title, message = "") {
  const node = document.createElement("div");
  node.className = `toast ${type || ""}`;
  node.innerHTML = `<strong>${escapeHtml(title)}</strong>${message ? `<span>${escapeHtml(message)}</span>` : ""}`;
  $("toastHost").appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

function navigate(route, {replace = false} = {}) {
  if (!routeNames.has(route)) route = "today";
  state.route = route;
  document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.dataset.page === route));
  document.querySelectorAll(".nav-item[data-route]").forEach((button) => button.classList.toggle("active", button.dataset.route === route));
  if (replace) history.replaceState(null, "", `#${route}`); else if (location.hash !== `#${route}`) history.pushState(null, "", `#${route}`);
  $("sidebar").classList.remove("open");
  window.scrollTo({top:0, behavior:"instant"});
  if (route === "forecast") renderForecast();
  if (route === "methods") renderMethods();
  if (route === "supply") renderSupply();
  if (route === "performance") renderPerformance();
  if (route === "assistant") renderAssistantContext();
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { const body = await response.json(); detail = body.detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
}

async function loadWorkspace() {
  try {
    state.workspace = await api("/api/workspace");
    state.plans = state.workspace.plans || [];
    state.integrations = state.workspace.integrations || [];
    state.selectedPlan = state.plans[0] || null;
    $("siteName").textContent = state.workspace.site?.name || "Qazvin Manufacturing Site";
    $("todayDate").textContent = `${formatDate(state.workspace.today, {day:true})} · ${state.workspace.jalali_today || "Jalali calendar"}`;
    renderPlans();
    renderIntegrations();
  } catch (error) { toast("error", "Workspace unavailable", error.message); }
}

async function loadLatestRun() {
  try {
    state.result = await api("/api/runs/latest");
    state.activeItem = "__all__";
    renderAll();
  } catch (_) { renderAll(); }
}

function renderAll() {
  renderContext();
  renderToday();
  renderPlans();
  renderForecast();
  renderMethods();
  renderSupply();
  renderScenarios();
  renderPerformance();
  renderIntegrations();
  renderAssistantContext();
}

function renderContext() {
  const r = state.result;
  const latestPlan = state.plans[0];
  $("planContext").textContent = latestPlan ? `${latestPlan.name} · ${latestPlan.status}` : r ? `Forecast ${r.run_id}` : "No active plan";
  const pill = $("freshnessPill");
  pill.classList.toggle("ready", Boolean(r));
  pill.querySelector("span").textContent = r?.summary?.end ? `${r.source_classification === "synthetic_sample" ? "Synthetic sample · " : ""}Data through ${formatDate(r.summary.end)}` : "No data";
  $("navDataState").classList.toggle("ready", Boolean(r));
  $("exportBtn").disabled = !r?.run_id;
  $("createPlanBtn").disabled = !r?.run_id;
  $("addOverrideBtn").disabled = !r;
  $("saveViewBtn").disabled = !r;
  $("applyScenarioBtn").disabled = !state.historyFile;
}

function buildDecisions() {
  const r = state.result; if (!r) return [];
  const rows = [];
  const evidence = r.metrics?.evidence_level || "limited";
  if (evidence === "limited") rows.push({priority:"high", item:"Whole plan", reason:r.metrics?.evidence_reason || "Validation evidence is limited.", owner:"Demand planner", target:"methods"});
  const warnings = r.warnings || [];
  warnings.slice(0, 3).forEach((warning) => rows.push({priority:warning.includes("missing future") ? "high" : "medium", item:"Data input", reason:warning, owner:"Data owner", target:"data"}));
  Object.entries(r.series_diagnostics || {}).forEach(([id, d]) => {
    const meta = r.metadata?.[id] || {};
    const label = meta.sku || id;
    if (Number(d.quality_score) < 65) rows.push({priority:"high", item:label, reason:`Forecast quality is ${number(d.quality_score)} / 100.`, owner:"Demand planner", target:"forecast", id});
    else if (Math.abs(Number(d.bias_pct)) > 15) rows.push({priority:"medium", item:label, reason:`Forecast bias is ${pct(d.bias_pct)}.`, owner:"Demand planner", target:"performance", id});
    if (["intermittent", "lumpy"].includes(d.demand_class)) rows.push({priority:"medium", item:label, reason:`${humanize(d.demand_class)} demand needs an intermittent method review.`, owner:"Demand planner", target:"methods", id});
    if (d.structural_break_suspected) rows.push({priority:"high", item:label, reason:"Recent demand shifted materially from the prior operating window.", owner:"Demand planner", target:"performance", id});
    if (d.stockout_or_lost_sales_suspected) rows.push({priority:"medium", item:label, reason:`${number(d.isolated_zero_periods)} isolated zero period(s) may hide a stockout or lost sale.`, owner:"Supply planner", target:"supply", id});
  });
  (r.operations?.actions || []).slice(0, 5).forEach((action) => rows.push({priority:action.priority || "medium", item:action.subject, reason:action.action, owner:action.owner, target:"supply"}));
  return rows.slice(0, 14);
}

function renderToday() {
  const r = state.result;
  const decisions = buildDecisions();
  const latestPlan = state.plans[0];
  $("todayPlanStatus").textContent = latestPlan ? humanize(latestPlan.status) : r ? "Forecast ready" : "Not started";
  $("todayPlanNote").textContent = latestPlan ? latestPlan.name : r ? "Save as a plan version" : "Create a forecast to begin";
  $("todayEvidence").textContent = r ? humanize(r.metrics?.evidence_level || "Limited") : "—";
  $("todayEvidenceNote").textContent = r ? `${r.metrics?.rolling_folds || 0} rolling validation window(s)` : "No validation result";
  $("todayRiskCount").textContent = decisions.length;
  $("todayDataQuality").textContent = r?.summary?.data_quality_score != null ? `${number(r.summary.data_quality_score)} / 100` : "—";
  $("todayDataNote").textContent = r ? `${number(r.summary?.rows)} rows · ${number(r.summary?.series)} series` : "No source loaded";
  $("decisionCount").textContent = `${decisions.length} open`;
  $("navDecisionCount").textContent = decisions.length;
  $("decisionTable").innerHTML = decisions.length ? decisions.map((d, index) => `<tr data-decision="${index}"><td><span class="priority ${d.priority}">${humanize(d.priority)}</span></td><td><div class="cell-title"><strong>${escapeHtml(d.item)}</strong></div></td><td>${escapeHtml(d.reason)}</td><td>${escapeHtml(d.owner)}</td><td><button class="text-link" data-decision-open="${index}">Review</button></td></tr>`).join("") : emptyRow(5, r ? "No material forecast exceptions were found." : "Load data to create the decision queue.");
  document.querySelectorAll("[data-decision-open]").forEach((button) => button.addEventListener("click", () => {
    const d = decisions[Number(button.dataset.decisionOpen)]; if (d?.id) state.activeItem = d.id; navigate(d?.target || "forecast");
  }));
  const cycleStage = latestPlan?.status === "published" ? 4 : latestPlan?.status === "approved" || latestPlan?.status === "review" ? 3 : latestPlan ? 2 : r ? 2 : 1;
  document.querySelectorAll("#cycleList li").forEach((li, index) => { li.classList.toggle("active", index + 1 === cycleStage); li.classList.toggle("done", index + 1 < cycleStage); });
  const coverage = Object.values(r?.driver_coverage || {});
  const factorCoverage = coverage.length ? Math.min(...coverage.map((d) => Number(d.coverage_pct) || 0)) : null;
  $("sourceHealth").innerHTML = `<div><span>Historical demand</span><b class="${r ? "" : "neutral"}">${r ? `${number(r.summary?.rows)} reviewed rows` : "Not connected"}</b></div><div><span>Future factors</span><b class="${r ? "" : "neutral"}">${factorCoverage == null ? (r ? "Not used" : "Not connected") : `${number(factorCoverage, 1)}% supplied`}</b></div><div><span>Iran context</span><b>Qazvin configured</b></div>`;
}

function renderPlans() {
  const plans = state.plans || [];
  $("plansTable").innerHTML = plans.length ? plans.map((plan) => `<tr data-click data-plan-id="${escapeHtml(plan.id)}"><td><div class="cell-title"><strong>${escapeHtml(plan.name)}</strong><small>${escapeHtml(plan.id)} · run ${escapeHtml(plan.run_id)}</small></div></td><td><span class="status ${escapeHtml(plan.status)}">${escapeHtml(humanize(plan.status))}</span></td><td>${number(plan.settings?.horizon)} ${escapeHtml(plan.settings?.frequency || "periods")}</td><td><span class="status ${evidenceClass(plan.metrics?.evidence_level)}">${escapeHtml(humanize(plan.metrics?.evidence_level || "limited"))}</span></td><td>${escapeHtml(plan.owner)}</td><td>${formatDate(plan.updated_at, {day:true})}</td></tr>`).join("") : emptyRow(6, "No plan versions yet.");
  document.querySelectorAll("[data-plan-id]").forEach((row) => row.addEventListener("click", () => selectPlan(row.dataset.planId)));
  updateSelectedPlanPanel();
}
function selectPlan(id) { state.selectedPlan = state.plans.find((plan) => plan.id === id) || null; updateSelectedPlanPanel(); }
function updateSelectedPlanPanel() {
  const plan = state.selectedPlan;
  $("selectedPlanName").textContent = plan ? `${plan.name} · ${humanize(plan.status)}` : "Select a plan to review.";
  const allowed = {draft:["review"],review:["approved"],approved:["published"],published:[],archived:[]};
  document.querySelectorAll("[data-plan-status]").forEach((button) => { button.disabled = !plan || !(allowed[plan.status] || []).includes(button.dataset.planStatus); });
  $("addPlanCommentBtn").disabled = !plan;
  $("planActionNote").textContent = plan?.metrics?.evidence_level === "limited" ? "Approval is blocked: this run has limited validation evidence." : "Every transition is timestamped and retained in the plan history.";
  if (!plan) { $("planComparison").innerHTML = ""; $("planHistory").innerHTML = `<p class="empty-copy">Approval history appears here.</p>`; return; }
  const previous = state.plans.find((row) => row.id !== plan.id && row.site_id === plan.site_id);
  const delta = previous && Number.isFinite(Number(previous.metrics?.wape_pct)) ? Number(plan.metrics?.wape_pct || 0) - Number(previous.metrics.wape_pct) : null;
  const comparisonText = delta == null ? "same validation basis" : Math.abs(delta) < 0.05 ? "same WAPE" : `${delta < 0 ? "better" : "higher"} WAPE by ${pct(Math.abs(delta))}`;
  $("planComparison").innerHTML = previous ? `Compared with <strong>${escapeHtml(previous.name)}</strong>: ${comparisonText}; ${number(plan.overrides?.filter((row) => !row.reverted_at).length || 0)} active override(s).` : `First plan version for this site · ${number(plan.overrides?.filter((row) => !row.reverted_at).length || 0)} active override(s).`;
  const activeOverrides = (plan.overrides || []).filter((row) => !row.reverted_at);
  const overrideRows = activeOverrides.map((row) => `<article><strong>Override · ${escapeHtml(row.item_id)}</strong><span>${escapeHtml(formatDate(row.period))} · ${number(row.value,1)} · ${escapeHtml(row.reason)}</span>${!["published","archived"].includes(plan.status) ? `<button class="text-link" data-revert-override="${escapeHtml(row.id)}">Reverse override</button>` : ""}</article>`).join("");
  const historyRows = (plan.history || []).slice().reverse().slice(0,8).map((row) => `<article><strong>${escapeHtml(humanize(row.status))} · ${escapeHtml(row.actor)}</strong><span>${escapeHtml(row.note || "Status updated")} · ${escapeHtml(formatDate(row.at,{day:true}))}</span></article>`).join("");
  $("planHistory").innerHTML = overrideRows + historyRows || `<p class="empty-copy">No plan activity yet.</p>`;
  $("planHistory").querySelectorAll("[data-revert-override]").forEach((button) => button.addEventListener("click", () => revertPlanOverride(button.dataset.revertOverride)));
}

function idsForView(viewId) {
  const r = state.result; if (!r) return [];
  if (viewId === "__all__") return r.items || [];
  if (viewId.startsWith("__category__:")) return (r.items || []).filter((id) => r.metadata?.[id]?.category === viewId.split(":").slice(1).join(":"));
  if (viewId.startsWith("__customer__:")) return (r.items || []).filter((id) => r.metadata?.[id]?.customer === viewId.split(":").slice(1).join(":"));
  if (viewId.startsWith("__warehouse__:")) return (r.items || []).filter((id) => r.metadata?.[id]?.warehouse === viewId.split(":").slice(1).join(":"));
  return [viewId];
}
function aggregateSeries(ids) {
  const r = state.result; if (!r || !ids.length) return null;
  const historyMap = new Map(), forecastMap = new Map();
  ids.forEach((id) => {
    (r.series?.[id]?.history || []).forEach((row) => historyMap.set(row.timestamp, (historyMap.get(row.timestamp) || 0) + Number(row.target || 0)));
    (r.series?.[id]?.forecast || []).forEach((row) => {
      const current = forecastMap.get(row.timestamp) || {timestamp:row.timestamp,baseline_mean:0,mean:0,p10:0,p50:0,p90:0};
      ["baseline_mean","mean","p10","p50","p90"].forEach((key) => { current[key] += Number(row[key] ?? row.mean ?? 0); });
      forecastMap.set(row.timestamp,current);
    });
  });
  return {history:[...historyMap].sort().map(([timestamp,target]) => ({timestamp,target})),forecast:[...forecastMap.values()].sort((a,b) => a.timestamp.localeCompare(b.timestamp)),methods:{}};
}
function seriesForId(viewId) {
  const r = state.result; if (!r) return null;
  if (r.series?.[viewId]) return r.series[viewId];
  return aggregateSeries(idsForView(viewId));
}
function activeSeries() { return seriesForId(state.activeItem); }
function itemLabel(id) {
  if (id.startsWith("__category__:")) return `Category · ${id.split(":").slice(1).join(":")}`;
  if (id.startsWith("__customer__:")) return `Customer · ${id.split(":").slice(1).join(":")}`;
  if (id.startsWith("__warehouse__:")) return `Warehouse · ${id.split(":").slice(1).join(":")}`;
  const meta = state.result?.metadata?.[id] || {}; return meta.sku ? `${meta.sku}${meta.customer ? ` · ${meta.customer}` : ""}` : id === "__all__" ? "All demand" : id;
}
function approvedValue(viewId, timestamp, planValue) {
  const plan = state.selectedPlan || state.plans[0];
  if (!plan || plan.run_id !== state.result?.run_id || !["approved","published"].includes(plan.status)) return planValue;
  const ids = new Set(idsForView(viewId)); let value = Number(planValue || 0);
  (plan.overrides || []).filter((row) => !row.reverted_at && ids.has(row.item_id) && String(row.period).slice(0,10) === String(timestamp).slice(0,10)).forEach((row) => {
    const original = state.result?.series?.[row.item_id]?.forecast?.find((point) => String(point.timestamp).slice(0,10) === String(timestamp).slice(0,10));
    if (original) value += Number(row.value) - Number(original.mean || 0);
  });
  return value;
}

function renderForecast() {
  const r = state.result;
  const select = $("forecastItemSelect");
  if (r) {
    const current = state.activeItem;
    const groups = (field,prefix) => [...new Set((r.items || []).map((id) => r.metadata?.[id]?.[field]).filter(Boolean))].sort().map((name) => `<option value="${prefix}:${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
    const saved = state.savedViews.filter((view) => idsForView(view.id).length).map((view) => `<option value="${escapeHtml(view.id)}">${escapeHtml(view.label)}</option>`).join("");
    select.innerHTML = `<option value="__all__">All demand</option>${saved ? `<optgroup label="Saved views">${saved}</optgroup>` : ""}<optgroup label="Categories">${groups("category","__category__")}</optgroup><optgroup label="Customers">${groups("customer","__customer__")}</optgroup><optgroup label="Warehouses">${groups("warehouse","__warehouse__")}</optgroup><optgroup label="Items">${(r.items || []).map((id) => `<option value="${escapeHtml(id)}">${escapeHtml(itemLabel(id))}</option>`).join("")}</optgroup>`;
    select.value = seriesForId(current) ? current : "__all__"; state.activeItem = select.value;
  }
  const series = activeSeries();
  if (!r || !series) {
    $("forecastSubtitle").textContent = "Load data to review a demand stream.";
    ["forecastTotal", "forecastChange", "forecastRange", "forecastMethod"].forEach((id) => $(id).textContent = "—");
    $("forecastValues").innerHTML = emptyRow(6, "No forecast values.");
    $("driverList").innerHTML = `<p class="empty-copy">No approved factors yet.</p>`;
    drawChart(null); return;
  }
  $("forecastSubtitle").textContent = `${itemLabel(state.activeItem)} · ${r.run_settings?.horizon || series.forecast.length} ${r.run_settings?.frequency || "periods"}`;
  const horizon = series.forecast.length;
  const total = series.forecast.reduce((sum, row) => sum + Number(row.mean || 0), 0);
  const low = series.forecast.reduce((sum, row) => sum + Number(row.p10 || 0), 0);
  const high = series.forecast.reduce((sum, row) => sum + Number(row.p90 || 0), 0);
  const prior = series.history.slice(-horizon).reduce((sum, row) => sum + Number(row.target || 0), 0);
  const change = prior ? (total / prior - 1) * 100 : 0;
  $("forecastTotal").textContent = compact(total);
  $("forecastChange").textContent = `${change >= 0 ? "+" : ""}${pct(change)}`;
  $("forecastRange").textContent = `${compact(low)}–${compact(high)}`;
  $("forecastMethod").textContent = r.best_model || "Recommended";
  $("forecastMethodNote").textContent = `${r.metrics?.rolling_folds || 0} validation window(s)`;
  const level = evidenceClass(r.metrics?.evidence_level);
  $("evidenceNotice").className = `notice evidence-notice ${level}`;
  $("evidenceTitle").textContent = `${humanize(level)} forecast evidence`;
  $("evidenceCopy").textContent = r.metrics?.evidence_reason || "Validation evidence has not been graded.";
  $("forecastValues").innerHTML = series.forecast.map((row) => `<tr><td>${formatDate(row.timestamp)}</td><td class="num">${number(row.baseline_mean ?? row.mean, 1)}</td><td class="num">${number(row.mean, 1)}</td><td class="num">${number(approvedValue(state.activeItem,row.timestamp,row.mean), 1)}</td><td class="num">${number(row.p10, 1)}</td><td class="num">${number(row.p90, 1)}</td></tr>`).join("");
  $("overridePeriod").innerHTML = series.forecast.map((row) => `<option value="${escapeHtml(row.timestamp)}">${formatDate(row.timestamp)}</option>`).join("");
  $("overrideValue").value = series.forecast[0] ? Number(series.forecast[0].mean).toFixed(1) : "";
  renderDrivers();
  drawChart(series);
}

function renderDrivers() {
  const rows = state.result?.drivers || [];
  const max = Math.max(...rows.map((row) => Number(row.importance) || 0), 1e-9);
  $("driverList").innerHTML = rows.length ? rows.slice(0, 7).map((row) => `<div class="driver-row"><div class="driver-name"><strong>${escapeHtml(humanize(row.feature))}</strong><small>${escapeHtml(humanize(row.role))} · ${escapeHtml(row.direction)} association</small></div><span class="driver-bar"><i style="width:${Math.max(4, Number(row.importance) / max * 100)}%"></i></span><b>${number(Number(row.importance) / max * 100)}%</b></div>`).join("") : `<p class="empty-copy">No approved factors were used in this run.</p>`;
}

function drawChart(series) {
  const svg = $("forecastChart");
  if (!series?.history?.length || !series?.forecast?.length) {
    svg.innerHTML = `<text x="600" y="215" text-anchor="middle" class="chart-axis">No forecast data</text>`; return;
  }
  const historyRows = series.history.slice(-36);
  const forecastRows = series.forecast;
  const values = [...historyRows.map((r) => Number(r.target)), ...forecastRows.flatMap((r) => [Number(r.p10), Number(r.p90)])].filter(Number.isFinite);
  let min = Math.min(...values, 0), max = Math.max(...values, 1); const pad = Math.max((max - min) * .12, max * .04, 1); max += pad; min = Math.max(0, min - pad);
  const W = 1200, H = 430, left = 64, right = 24, top = 22, bottom = 52, plotW = W - left - right, plotH = H - top - bottom;
  const totalPoints = historyRows.length + forecastRows.length;
  const x = (index) => left + (index / Math.max(1, totalPoints - 1)) * plotW;
  const y = (value) => top + (1 - (Number(value) - min) / Math.max(1e-9, max - min)) * plotH;
  const path = (points) => points.map((p, i) => `${i ? "L" : "M"}${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const histPoints = historyRows.map((row, i) => ({i, v:Number(row.target)}));
  const anchorIndex = historyRows.length - 1;
  const forecastPoints = [{i:anchorIndex, v:Number(historyRows.at(-1).target)}, ...forecastRows.map((row, step) => ({i:historyRows.length + step, v:Number(row.mean)}))];
  const statisticalPoints = [{i:anchorIndex, v:Number(historyRows.at(-1).target)}, ...forecastRows.map((row, step) => ({i:historyRows.length + step, v:Number(row.baseline_mean ?? row.mean)}))];
  const approvedPoints = [{i:anchorIndex, v:Number(historyRows.at(-1).target)}, ...forecastRows.map((row, step) => ({i:historyRows.length + step, v:approvedValue(state.activeItem,row.timestamp,row.mean)}))];
  const hasAdjustment = forecastRows.some((row) => Math.abs(Number(row.baseline_mean ?? row.mean) - Number(row.mean)) > 1e-6);
  const hasApprovalChange = forecastRows.some((row) => Math.abs(approvedValue(state.activeItem,row.timestamp,row.mean) - Number(row.mean)) > 1e-6);
  const upper = [{i:anchorIndex, v:Number(historyRows.at(-1).target)}, ...forecastRows.map((row, step) => ({i:historyRows.length + step, v:Number(row.p90)}))];
  const lower = [{i:anchorIndex, v:Number(historyRows.at(-1).target)}, ...forecastRows.map((row, step) => ({i:historyRows.length + step, v:Number(row.p10)}))].reverse();
  const band = `${path(upper)} ${lower.map((p) => `L${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ")} Z`;
  let html = "";
  for (let i = 0; i <= 4; i++) { const value = min + (max - min) * (4 - i) / 4; const yy = top + plotH * i / 4; html += `<line x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}" class="chart-grid"/><text x="${left-10}" y="${yy+4}" text-anchor="end" class="chart-axis">${escapeHtml(compact(value))}</text>`; }
  const allDates = [...historyRows.map((r) => r.timestamp), ...forecastRows.map((r) => r.timestamp)];
  const labelCount = window.innerWidth < 600 ? 4 : 7;
  for (let j = 0; j < labelCount; j++) { const i = Math.round(j * (totalPoints - 1) / Math.max(1, labelCount - 1)); html += `<text x="${x(i)}" y="${H-18}" text-anchor="middle" class="chart-axis">${escapeHtml(formatDate(allDates[i], {short:true}))}</text>`; }
  html += `<path d="${band}" class="chart-band"/><line x1="${x(anchorIndex)}" y1="${top}" x2="${x(anchorIndex)}" y2="${top+plotH}" class="chart-separator"/><path d="${path(histPoints)}" class="chart-history"/>${hasAdjustment ? `<path d="${path(statisticalPoints)}" class="chart-statistical"/>` : ""}<path d="${path(forecastPoints)}" class="chart-forecast"/>${hasApprovalChange ? `<path d="${path(approvedPoints)}" class="chart-approved"/>` : ""}<circle cx="${x(anchorIndex)}" cy="${y(historyRows.at(-1).target)}" r="4.5" class="chart-anchor"/>`;
  const points = [...historyRows.map((row, i) => ({i, date:row.timestamp, value:row.target, type:"Actual"})), ...forecastRows.map((row, step) => ({i:historyRows.length + step, date:row.timestamp, value:row.mean, low:row.p10, high:row.p90, type:"Forecast"}))];
  points.forEach((point, index) => { const start = index === 0 ? left : (x(point.i - .5)); const end = index === points.length - 1 ? W - right : x(point.i + .5); html += `<rect x="${start}" y="${top}" width="${Math.max(1,end-start)}" height="${plotH}" class="chart-hover" data-chart-point="${index}"/>`; });
  svg.innerHTML = html;
  svg.querySelectorAll("[data-chart-point]").forEach((rect) => {
    rect.addEventListener("mousemove", (event) => { const p = points[Number(rect.dataset.chartPoint)]; const tip = $("chartTooltip"); tip.innerHTML = `<strong>${escapeHtml(formatDate(p.date))} · ${escapeHtml(p.type)}</strong>${number(p.value,1)} tonnes${p.low != null ? `<br><span>${number(p.low,1)}–${number(p.high,1)}</span>` : ""}`; tip.classList.remove("hidden"); const box = $("forecastChart").getBoundingClientRect(); tip.style.left = `${Math.min(box.width - 170, Math.max(8, event.clientX - box.left + 10))}px`; tip.style.top = `${Math.max(8, event.clientY - box.top - 55)}px`; });
    rect.addEventListener("mouseleave", () => $("chartTooltip").classList.add("hidden"));
  });
}

function renderMethods() {
  const r = state.result, metrics = r?.metrics || {};
  $("methodSelected").textContent = r?.best_model || "—";
  $("methodValidation").textContent = r ? `${metrics.rolling_folds || 0} × ${metrics.validation_horizon || 0} periods` : "—";
  $("methodEvidence").textContent = r ? humanize(metrics.evidence_level || "limited") : "—";
  const baseline = r?.leaderboard?.find((row) => row.model === "Seasonal naive");
  $("methodBaseline").textContent = baseline ? `${pct(baseline.wape_pct)} WAPE` : "—";
  $("methodCoverage").textContent = r ? `${pct(metrics.interval_coverage_pct)} observed · ${pct(metrics.interval_target_pct)} target` : "80% interval target";
  $("methodApply").value = r?.method_selection && ["recommended","seasonal","trend","intermittent","driver"].includes(r.method_selection) ? r.method_selection : "recommended";
  $("methodTable").innerHTML = r?.leaderboard?.length ? r.leaderboard.map((row, index) => `<tr><td><div class="cell-title"><strong>${escapeHtml(row.model)}</strong><small>${index === 0 ? "Best single candidate" : row.weight > 0 ? "Included in selected mix" : "Compared"}</small></div></td><td class="num">${pct(row.wape_pct)}</td><td class="num">${pct(row.bias_pct)}</td><td class="num">${pct(row.smape_pct)}</td><td class="num">${pct(row.stability_pct)}</td><td class="num">${pct(Number(row.weight || 0) * 100)}</td><td><button class="text-link apply-model" data-model="${escapeHtml(row.model)}" ${state.historyFile ? "" : "disabled"}>Use</button></td></tr>`).join("") : emptyRow(7, "Run a forecast to compare methods.");
  $("horizonMethodTable").innerHTML = metrics.horizon_metrics?.length ? metrics.horizon_metrics.map((row) => `<tr><td>Month ${number(row.step)}</td><td class="num">${pct(row.wape_pct)}</td><td class="num">${pct(row.bias_pct)}</td><td class="num">${number(row.mae,1)}</td><td class="num">${number(row.validation_points)}</td></tr>`).join("") : emptyRow(5, "Run a forecast to review horizon error.");
  document.querySelectorAll(".apply-model").forEach((button) => button.addEventListener("click", () => executeForecast({method:`model:${button.dataset.model}`})));
}

function supplyRows() {
  const r = state.result; if (!r) return [];
  return (r.items || []).map((id) => {
    const meta = r.metadata?.[id] || {}, forecast = r.series?.[id]?.forecast?.[0];
    const demand = Number(forecast?.mean || 0), inventory = Number(meta.inventory_on_hand_tonnes || 0), safety = Number(meta.safety_stock_tonnes || 0), capacity = Number(meta.monthly_capacity_tonnes || 0), lead = Number(meta.lead_time_days || 0), service = Number(meta.service_level_target || 0);
    const projected = inventory - demand, capacityUse = capacity ? demand / capacity * 100 : null, daysCover = demand > 0 ? Math.max(0, projected) / (demand / 30) : null;
    const risk = projected < safety || (capacityUse != null && capacityUse > 90);
    let action = "No action"; if (projected < 0) action = capacityUse > 100 ? "Expedite + add capacity" : "Expedite supply"; else if (projected < safety && capacityUse > 100) action = "Capacity + stock review"; else if (capacityUse > 100) action = "Resolve capacity"; else if (projected < safety) action = "Replenish stock"; else if (capacityUse > 90) action = "Review schedule";
    return {id, meta, demand, inventory, projected, daysCover, safety, service, capacityUse, lead, risk, action};
  });
}
function renderSupply() {
  let rows = supplyRows();
  const filter = $("supplyFilter").value; if (filter === "risk") rows = rows.filter((row) => row.risk);
  const all = supplyRows();
  $("supplyShortages").textContent = state.result ? all.filter((row) => row.inventory - row.demand < row.safety).length : "—";
  const operations = state.result?.operations || {}, opSummary = operations.summary || {};
  $("materialShortages").textContent = state.result ? number(opSummary.material_shortages || 0) : "—";
  $("supplyCapacity").textContent = state.result ? number(opSummary.capacity_bottlenecks || 0) : "—";
  $("qualityHold").textContent = state.result ? `${number(opSummary.quality_hold_total || 0,1)} t` : "—";
  $("supplyTable").innerHTML = rows.length ? rows.map((row) => `<tr><td><div class="cell-title"><strong>${escapeHtml(row.meta.sku || row.id)}</strong><small>${escapeHtml(row.meta.production_line || row.meta.category || "No line mapped")}</small></div></td><td class="num">${number(row.demand,1)}</td><td class="num">${number(row.projected,1)}</td><td class="num">${row.daysCover == null ? "—" : `${number(row.daysCover,1)} d`}</td><td class="num">${number(row.safety,1)}</td><td class="num">${row.service ? pct(row.service * 100) : "—"}</td><td class="num">${row.capacityUse == null ? "—" : pct(row.capacityUse)}</td><td class="num">${row.lead ? `${number(row.lead)} d` : "—"}</td><td><span class="status ${row.risk ? "risk" : "strong"}">${escapeHtml(row.action)}</span></td></tr>`).join("") : emptyRow(9, state.result ? "No items match this filter." : "Operational fields appear when data is loaded.");
  $("mrpSource").textContent = operations.source ? "Time-phased MRP" : "Operations master required";
  const materials = operations.materials || [];
  $("materialTable").innerHTML = materials.length ? materials.map((row) => `<tr><td><div class="cell-title"><strong>${escapeHtml(row.material_name || row.material_id)}</strong><small>${escapeHtml(row.supplier || "No supplier")} · ${number(row.lead_time_days)} d lead</small></div></td><td>${formatDate(row.period)}</td><td class="num">${number(row.gross_requirement,1)}</td><td class="num">${number(row.scheduled_receipts,1)}</td><td class="num">${number(row.projected_balance,1)}</td><td class="num">${number(row.shortage,1)}</td><td class="num">${number(row.recommended_order,1)}</td><td>${row.planned_release_date ? formatDate(row.planned_release_date,{day:true}) : "—"}</td><td><span class="status ${row.status === "shortage" ? "risk" : "strong"}">${escapeHtml(humanize(row.status))}</span></td></tr>`).join("") : emptyRow(9,"Upload an operations master to calculate material requirements.");
  const capacity = operations.capacity || [];
  $("capacityTable").innerHTML = capacity.length ? capacity.map((row) => `<tr><td><strong>${escapeHtml(row.production_line)}</strong></td><td>${formatDate(row.period)}</td><td class="num">${number(row.forecast_tonnes,1)}</td><td class="num">${number(row.available_tonnes,1)}</td><td class="num">${row.utilisation_pct == null ? "—" : pct(row.utilisation_pct)}</td><td class="num">${number(row.planned_downtime_hours,1)} h</td><td class="num">${number(row.gap_tonnes,1)}</td><td><span class="status ${row.status === "bottleneck" ? "risk" : row.status === "watch" ? "moderate" : "strong"}">${escapeHtml(humanize(row.status))}</span></td></tr>`).join("") : emptyRow(8,"Upload an operations master to calculate capacity.");
}

function scenarioSummary(result, name) {
  const series = result.series?.__all__; const total = series?.forecast?.reduce((sum,row) => sum + Number(row.mean||0),0) || 0;
  const low = series?.forecast?.reduce((sum,row) => sum + Number(row.p10||0),0) || 0; const high = series?.forecast?.reduce((sum,row) => sum + Number(row.p90||0),0) || 0;
  let closingStock = 0, stockRisks = 0, capacityRisks = 0, costExposure = 0;
  (result.items || []).forEach((id) => {
    const meta = result.metadata?.[id] || {}, itemForecast = result.series?.[id]?.forecast || [], nextDemand = Number(itemForecast[0]?.mean || 0), projected = Number(meta.inventory_on_hand_tonnes || 0) - nextDemand;
    closingStock += projected; if (projected < Number(meta.safety_stock_tonnes || 0)) stockRisks += 1;
    if (Number(meta.monthly_capacity_tonnes || 0) > 0 && nextDemand / Number(meta.monthly_capacity_tonnes) > .9) capacityRisks += 1;
    costExposure += itemForecast.reduce((sum,row) => sum + Number(row.mean || 0),0) * Number(meta.unit_cost_irr || 0);
  });
  return {name, total, low, high, closingStock, stockRisks, capacityRisks, costExposure, adjustment:Number(result.scenario?.adjustment_pct || 0), run_id:result.run_id};
}
function renderScenarios() {
  const rows = []; if (state.result) rows.push(scenarioSummary(state.result, "Current baseline")); rows.push(...state.scenarios);
  const baseline = rows[0]?.total || 0;
  $("scenarioTable").innerHTML = rows.length ? rows.map((row,index) => `<tr><td><div class="cell-title"><strong>${escapeHtml(row.name)}</strong><small>${index === 0 ? "Statistical baseline" : `Run ${row.run_id}`}</small></div></td><td class="num">${number(row.total,1)}</td><td class="num">${baseline ? `${row.total >= baseline ? "+" : ""}${pct((row.total/baseline-1)*100)}` : "—"}</td><td class="num">${number(row.closingStock,1)}</td><td class="num">${number(row.stockRisks)}</td><td class="num">${number(row.capacityRisks)}</td><td class="num">${compact(row.costExposure)} IRR</td><td><span class="status ${index === 0 ? "strong" : "moderate"}">${index === 0 ? "Baseline" : "Scenario"}</span></td></tr>`).join("") : emptyRow(8, "Run a forecast to establish the baseline.");
}

function renderPerformance() {
  const r = state.result, m = r?.metrics || {};
  $("perfWape").textContent = r ? pct(m.wape_pct) : "—"; $("perfBias").textContent = r ? pct(m.bias_pct) : "—"; $("perfCoverage").textContent = r ? pct(m.interval_coverage_pct) : "—"; $("perfPoints").textContent = r ? number(m.validation_points) : "—";
  const rows = Object.entries(r?.series_diagnostics || {}).sort((a,b) => Number(a[1].quality_score)-Number(b[1].quality_score));
  $("performanceTable").innerHTML = rows.length ? rows.map(([id,d]) => `<tr><td><div class="cell-title"><strong>${escapeHtml(r.metadata?.[id]?.sku || id)}</strong><small>${escapeHtml(r.metadata?.[id]?.customer || "")}</small></div></td><td><div class="cell-title"><strong>${escapeHtml(humanize(d.demand_class))}</strong><small>${escapeHtml(humanize(d.lifecycle || "mature"))}${d.structural_break_suspected ? " · shift flagged" : ""}${d.stockout_or_lost_sales_suspected ? " · zero flagged" : ""}</small></div></td><td class="num">${pct(d.wape_pct)}</td><td class="num">${pct(d.bias_pct)}</td><td class="num">${pct(Number(d.seasonality_strength||0)*100)}</td><td>${escapeHtml(d.best_model || "—")}</td><td><span class="status ${Number(d.quality_score) >= 75 ? "strong" : Number(d.quality_score) >= 55 ? "moderate" : "risk"}">${number(d.quality_score)} / 100</span></td></tr>`).join("") : emptyRow(7, "No validation results yet.");
  const monitor = state.monitoring || {}, champion = monitor.champion, challenger = monitor.challenger;
  $("retrainBadge").textContent = monitor.retrain ? (monitor.retrain.recommended ? "Retraining recommended" : "Policy healthy") : "Waiting for runs";
  $("retrainBadge").className = `count-badge ${monitor.retrain?.recommended ? "status risk" : "status strong"}`;
  $("modelDuel").innerHTML = champion ? `<article><span>Champion</span><strong>${escapeHtml(champion.model)}</strong><small>${pct(champion.wape_pct)} WAPE · selected weight ${pct(Number(champion.weight||0)*100)}</small></article>${challenger ? `<article><span>Challenger</span><strong>${escapeHtml(challenger.model)}</strong><small>${pct(challenger.wape_pct)} WAPE · gap ${pct(Number(challenger.wape_pct)-Number(champion.wape_pct))}</small></article>` : ""}` : `<p class="empty-copy">Run a forecast to establish a champion.</p>`;
  $("monitoringTable").innerHTML = monitor.history?.length ? monitor.history.map((row) => `<tr><td><strong>${escapeHtml(row.run_id)}</strong></td><td>${formatDate(row.data_end)}</td><td>${escapeHtml(row.best_model || "—")}</td><td class="num">${pct(row.wape_pct)}</td><td class="num">${pct(row.bias_pct)}</td><td><span class="status ${evidenceClass(row.evidence)}">${escapeHtml(humanize(row.evidence || "limited"))}</span></td></tr>`).join("") : emptyRow(6,"No run history.");
  const intelligence = r?.product_intelligence || {}, relationships = intelligence.relationships || [], lifecycle = intelligence.lifecycle || [];
  const relRows = relationships.map((row) => ({product:row.sku,type:row.relationship_type,related:row.related_sku,effect:row.expected_effect_pct,evidence:row.evidence || "master data"}));
  const lifeRows = lifecycle.filter((row) => row.stage !== "mature" || row.analog).map((row) => ({product:row.sku,type:`${row.stage} lifecycle`,related:row.analog,effect:null,evidence:`${row.history_points || 0} history points`}));
  const combined = [...relRows,...lifeRows];
  $("intelligenceTable").innerHTML = combined.length ? combined.map((row) => `<tr><td><strong>${escapeHtml(row.product)}</strong></td><td>${escapeHtml(humanize(row.type))}</td><td>${escapeHtml(row.related || "—")}</td><td>${row.effect == null ? "—" : pct(row.effect)}</td><td>${escapeHtml(row.evidence)}</td></tr>`).join("") : emptyRow(5,r ? "No governed product relationships are loaded." : "Upload an operations master to add product relationships.");
}

async function loadMonitoring() {
  try { state.monitoring = await api(`/api/monitoring${state.result?.run_id ? `?run_id=${encodeURIComponent(state.result.run_id)}` : ""}`); renderPerformance(); }
  catch (_) { state.monitoring = null; renderPerformance(); }
}

function renderIntegrations() {
  const rows = state.integrations || [];
  $("connectorTable").innerHTML = rows.length ? rows.map((row) => `<tr><td><div class="cell-title"><strong>${escapeHtml(row.name)}</strong><small>${escapeHtml(row.path || row.url || row.secret_env || "Configuration saved")}</small></div></td><td>${escapeHtml(humanize(row.type))}</td><td>${row.enabled && row.schedule_minutes ? `Every ${number(row.schedule_minutes)} min` : "Manual"}</td><td>${row.last_sync ? formatDate(row.last_sync,{day:true}) : "Never"}</td><td><span class="status ${row.status === "healthy" ? "strong" : row.status === "failed" ? "risk" : "moderate"}">${escapeHtml(humanize(row.status || "not tested"))}</span></td><td><button class="text-link" data-sync-connector="${escapeHtml(row.id)}">Check now</button></td></tr>`).join("") : emptyRow(6,"No automated connections configured.");
  document.querySelectorAll("[data-sync-connector]").forEach((button) => button.addEventListener("click", () => syncConnector(button.dataset.syncConnector)));
}

async function refreshIntegrations() {
  try { state.integrations = (await api("/api/integrations")).integrations || []; renderIntegrations(); }
  catch (error) { toast("error","Connections unavailable",error.message); }
}

async function syncConnector(id) {
  try { const updated = await api(`/api/integrations/${encodeURIComponent(id)}/sync`,{method:"POST"}); state.integrations = state.integrations.map((row) => row.id === id ? updated : row); renderIntegrations(); toast("","Connection healthy",updated.name); }
  catch (error) { await refreshIntegrations(); toast("error","Connection check failed",error.message); }
}

async function saveConnector(event) {
  event.preventDefault();
  const type = $("connectorType").value, location = $("connectorLocation").value.trim();
  const payload = {name:$("connectorName").value.trim(),type,enabled:$("connectorEnabled").checked,schedule_minutes:Number($("connectorSchedule").value),secret_env:$("connectorSecret").value.trim() || undefined};
  if (type === "folder") payload.path = location; else payload.url = location;
  try { const saved = await api("/api/integrations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); state.integrations = state.integrations.filter((row) => row.id !== saved.id).concat(saved); $("connectorForm").classList.add("hidden"); renderIntegrations(); toast("","Connection saved",saved.name); }
  catch (error) { toast("error","Connection was not saved",error.message); }
}

async function calculateFva() {
  if (!state.result || !state.actualsFile) return;
  const form = new FormData(); form.append("actuals_file",state.actualsFile);
  try { const fva = await api(`/api/fva/${state.result.run_id}`,{method:"POST",body:form}); const direction = fva.fva_points >= 0 ? "improved" : "reduced"; $("fvaResult").innerHTML = `<strong>${fva.fva_points >= 0 ? "+" : ""}${number(fva.fva_points,2)} pts</strong><p>Planner decisions ${direction} WAPE from ${pct(fva.baseline_wape_pct)} to ${pct(fva.approved_wape_pct)} across ${number(fva.observations)} closed observations.</p>`; }
  catch (error) { toast("error","FVA could not be calculated",error.message); }
}

function renderAssistantContext() {
  if (!$("assistantEvidence")) return;
  const r = state.result, operations = r?.operations || {};
  $("assistantEvidence").textContent = r ? `Run ${r.run_id} · ${humanize(r.metrics?.evidence_level || "limited")} evidence` : "No current run.";
  $("assistantSources").innerHTML = `<div><span>Forecast & validation</span><b class="${r ? "" : "neutral"}">${r ? "Available" : "Missing"}</b></div><div><span>Operations master</span><b class="${operations.source ? "" : "neutral"}">${operations.source ? "Available" : "Missing"}</b></div><div><span>Plan register</span><b class="${state.plans.length ? "" : "neutral"}">${state.plans.length ? `${state.plans.length} plan(s)` : "No plans"}</b></div>`;
}

async function askAssistant(event) {
  if (event) event.preventDefault();
  const question = $("assistantQuestion").value.trim(); if (!question) return;
  $("assistantAnswer").innerHTML = `<p>Reviewing the current planning evidence…</p>`;
  try { const answer = await api("/api/assistant/query",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question,run_id:state.result?.run_id || null})}); $("assistantAnswer").innerHTML = `<p>${escapeHtml(answer.answer)}</p><div class="citations">${(answer.citations||[]).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`; }
  catch (error) { $("assistantAnswer").innerHTML = `<p>${escapeHtml(error.message)}</p>`; }
}

function setOptions(select, columns, preferences = [], blank = true) {
  const chosen = preferences.find((name) => columns.includes(name)) || (blank ? "" : columns[0] || "");
  select.innerHTML = `${blank ? '<option value="">Not mapped</option>' : ""}${columns.map((col) => `<option value="${escapeHtml(col)}">${escapeHtml(humanize(col))}</option>`).join("")}`;
  select.value = chosen;
}
function availableDrivers() {
  if (!state.historyPreview) return [];
  const mapped = new Set([$("dateCol").value,$("targetCol").value,$("itemCol").value,$("skuCol").value,$("categoryCol").value,$("customerCol").value].filter(Boolean));
  return state.historyPreview.columns.filter((col) => !mapped.has(col) && !metadataColumns.has(col));
}
function renderMapping() {
  const columns = state.historyPreview?.columns || [], future = state.futurePreview?.columns || [];
  const dateColumns = state.historyPreview?.date_candidates?.length ? state.historyPreview.date_candidates : columns;
  const targetColumns = state.historyPreview?.numeric_columns?.length ? state.historyPreview.numeric_columns : columns;
  const futureDateColumns = state.futurePreview?.date_candidates?.length ? state.futurePreview.date_candidates : future;
  const suggested = state.mappingSuggestions?.suggestions || {};
  setOptions($("dateCol"), dateColumns, [suggested.date,"date","month","period"].filter(Boolean), false);
  setOptions($("targetCol"), targetColumns, [suggested.target,"demand_tonnes","demand","sales","target"].filter(Boolean), false);
  setOptions($("itemCol"), columns, [suggested.item,"series_id","item_id","sku"].filter(Boolean), true);
  setOptions($("skuCol"), columns, [suggested.sku,"sku"].filter(Boolean), true); setOptions($("categoryCol"), columns, [suggested.category,"category"].filter(Boolean), true); setOptions($("customerCol"), columns, [suggested.customer,"customer"].filter(Boolean), true);
  setOptions($("futureDateCol"), futureDateColumns, ["date","month","period"], true); setOptions($("futureItemCol"), future, ["series_id","item_id","sku"], true);
  const available = new Set(availableDrivers());
  state.selectedDrivers = new Set([...(state.mappingSuggestions?.drivers || []),...preferredSignals].filter((name) => available.has(name)).slice(0,12));
  if (!state.selectedDrivers.size) state.selectedDrivers = new Set([...available].filter((name) => state.historyPreview.numeric_columns.includes(name)).slice(0,8));
  state.driverRoles = Object.fromEntries([...available].map((name) => [name,inferRole(name)]));
  renderSignals(); updateReadiness();
}
function renderSignals() {
  const drivers = availableDrivers();
  $("signalPicker").innerHTML = drivers.length ? drivers.map((name) => `<div class="signal-option"><label><input type="checkbox" value="${escapeHtml(name)}" ${state.selectedDrivers.has(name) ? "checked" : ""}/><span><strong>${escapeHtml(humanize(name))}</strong><small>${state.historyPreview.numeric_columns.includes(name) ? "Numeric signal" : "Category / event"}</small></span></label><button type="button" class="signal-role" data-signal-role="${escapeHtml(name)}">${escapeHtml(state.driverRoles[name] || inferRole(name))}</button></div>`).join("") : `<p class="empty-copy">Signals appear after file mapping.</p>`;
  $("signalPicker").querySelectorAll("input").forEach((input) => input.addEventListener("change", () => { input.checked ? state.selectedDrivers.add(input.value) : state.selectedDrivers.delete(input.value); updateReadiness(); }));
  $("signalPicker").querySelectorAll("[data-signal-role]").forEach((button) => button.addEventListener("click", () => { const name = button.dataset.signalRole; state.driverRoles[name] = state.driverRoles[name] === "external" ? "internal" : "external"; button.textContent = state.driverRoles[name]; }));
}
function updateReadiness() {
  const ready = Boolean(state.historyFile && $("dateCol").value && $("targetCol").value);
  $("mappingReadiness").classList.toggle("ready", ready); $("mappingReadiness").querySelector("span").textContent = ready ? `${number(state.historyPreview?.rows)} historical rows mapped. ${state.selectedDrivers.size} signal(s) selected.` : "Upload historical data and map date and demand fields.";
  $("runForecastBtn").disabled = !ready;
}

async function previewFile(file) { const form = new FormData(); form.append("file", file); return api("/api/preview", {method:"POST", body:form}); }
async function attachFile(kind, file) {
  if (!file) return;
  const nameEl = kind === "history" ? $("historyFileName") : $("futureFileName"), metaEl = kind === "history" ? $("historyFileMeta") : $("futureFileMeta"), card = kind === "history" ? $("historyCard") : $("futureCard");
  nameEl.textContent = file.name; metaEl.textContent = "Reading file…";
  try {
    const preview = await previewFile(file); state[`${kind}File`] = file; state[`${kind}Preview`] = preview; card.classList.add("ready"); metaEl.textContent = `${number(preview.rows)} rows · ${number(preview.columns.length)} columns${preview.selected_sheet ? ` · ${preview.selected_sheet}` : ""}`;
    if (kind === "history") state.mappingSuggestions = await api("/api/assistant/mapping",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({columns:preview.columns,numeric_columns:preview.numeric_columns || [],date_candidates:preview.date_candidates || []})});
    renderMapping(); toast("", `${kind === "history" ? "Historical" : "Future"} data ready`, file.name);
  } catch (error) { metaEl.textContent = error.message; card.classList.remove("ready"); toast("error", "Could not read file", error.message); }
}

async function attachOperations(file) {
  if (!file) return;
  $("operationsFileName").textContent = file.name; $("operationsFileMeta").textContent = "Checking workbook…";
  const form = new FormData(); form.append("file",file);
  try { const preview = await api("/api/operations/preview",{method:"POST",body:form}); state.operationsFile = file; state.operationsPreview = preview; $("operationsCard").classList.add("ready"); $("operationsFileMeta").textContent = `${number(preview.rows)} rows · ${preview.sheets.map((sheet) => humanize(sheet.name)).join(", ")}`; toast("","Operations master ready","BOM, purchasing and capacity sheets were validated."); }
  catch (error) { state.operationsFile = null; $("operationsCard").classList.remove("ready"); $("operationsFileMeta").textContent = error.message; toast("error","Operations workbook is not ready",error.message); }
}

async function loadIranDemo() {
  state.sourceClassification = "synthetic_sample";
  showLoader("Loading the Iran sample", "Preparing 60 months of history and 12 months of assumptions.");
  try {
    const [h,f,o] = await Promise.all([fetch("/api/sample/iran_history"),fetch("/api/sample/iran_future"),fetch("/api/sample/iran_operations")]);
    const historyBlob = await h.blob(), futureBlob = await f.blob(), operationsBlob = await o.blob();
    await attachFile("history", new File([historyBlob], "iran_manufacturing_history_60m.csv", {type:"text/csv"}));
    await attachFile("future", new File([futureBlob], "iran_manufacturing_scenario_12m.csv", {type:"text/csv"}));
    await attachOperations(new File([operationsBlob], "iran_operations_master.xlsx", {type:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}));
    $("horizon").value = 12; $("frequency").value = "monthly"; $("futurePolicy").value = "require"; $("methodSelection").value = "recommended";
    hideLoader(); toast("", "Iran sample loaded", "Review the mappings, then run the forecast.");
  } catch (error) { hideLoader(); toast("error", "Sample could not be loaded", error.message); }
}

function buildRunForm({method, adjustment, policy} = {}) {
  const form = new FormData(); form.append("historical_file", state.historyFile); if (state.futureFile) form.append("future_file", state.futureFile);
  if (state.operationsFile) form.append("operations_file", state.operationsFile);
  const fields = ["dateCol","targetCol","itemCol","skuCol","categoryCol","customerCol","futureDateCol","futureItemCol","frequency","horizon","profile"];
  const names = ["date_col","target_col","item_col","sku_col","category_col","customer_col","future_date_col","future_item_col","frequency","horizon","profile"];
  fields.forEach((id,index) => form.append(names[index], $(id).value || ""));
  const drivers = [...state.selectedDrivers]; form.append("driver_cols_json", JSON.stringify(drivers)); form.append("known_driver_cols_json", JSON.stringify(drivers)); form.append("driver_roles_json", JSON.stringify(Object.fromEntries(drivers.map((name) => [name,state.driverRoles[name] || inferRole(name)]))));
  form.append("missing_strategy","auto"); form.append("outlier_strategy","winsorize"); form.append("scenario_adjustment_pct", String(adjustment ?? 0)); form.append("method_selection", method || $("methodSelection").value); form.append("future_driver_policy", policy || $("futurePolicy").value);
  form.append("source_classification", state.sourceClassification);
  return form;
}

function showLoader(title, copy) {
  $("loaderTitle").textContent = title; $("loaderCopy").textContent = copy; $("loaderProgress").style.width = "8%"; $("loader").classList.remove("hidden");
  clearInterval(state.loaderTimer); let progress = 8; state.loaderTimer = setInterval(() => { progress = Math.min(91, progress + Math.max(1,(94-progress)*.08)); $("loaderProgress").style.width = `${progress}%`; }, 420);
}
function hideLoader() { clearInterval(state.loaderTimer); $("loaderProgress").style.width = "100%"; setTimeout(() => $("loader").classList.add("hidden"), 180); }

async function executeForecast({method, adjustment = 0, policy, scenario = false, scenarioName = "Scenario"} = {}) {
  if (!state.historyFile) { navigate("data"); toast("warning", "Source files required", "Load or import data before running a forecast."); return; }
  showLoader(scenario ? "Running the scenario" : "Building the forecast", "Testing open-source forecasting methods on historical windows.");
  try {
    const result = await api("/api/run", {method:"POST", body:buildRunForm({method,adjustment,policy})});
    if (scenario) { state.scenarios.push(scenarioSummary(result, scenarioName)); renderScenarios(); hideLoader(); toast("", "Scenario ready", `${scenarioName} was compared with the baseline.`); return; }
    state.result = result; state.activeItem = "__all__"; state.scenarios = []; renderAll(); await loadMonitoring(); hideLoader(); navigate("forecast"); toast("", "Forecast ready", `${humanize(result.metrics?.evidence_level || "limited")} evidence · ${result.metrics?.rolling_folds || 0} validation windows.`);
  } catch (error) { hideLoader(); toast("error", "Forecast could not be created", error.message); navigate("data"); }
}

async function createPlan() {
  if (!state.result) return;
  try {
    const plan = await api("/api/plans", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({name:$("planName").value,owner:$("planOwner").value,run_id:state.result.run_id,site_id:state.workspace?.site?.id || "qazvin-01"})});
    state.plans.unshift(plan); state.selectedPlan = plan; renderAll(); toast("", "Draft plan created", plan.name);
  } catch (error) { toast("error", "Plan could not be created", error.message); }
}
async function transitionPlan(status) {
  if (!state.selectedPlan) return;
  try {
    const plan = await api(`/api/plans/${state.selectedPlan.id}/status`, {method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({status,actor:$("planOwner").value || "Planning team",note:`Moved to ${status} from the planning workspace`})});
    state.plans = state.plans.map((row) => row.id === plan.id ? plan : row); state.selectedPlan = plan; renderAll(); toast("", `Plan ${humanize(status)}`, plan.name);
  } catch (error) { toast("error", "Plan status was not changed", error.message); }
}
async function addPlanComment() {
  if (!state.selectedPlan) return;
  const text = $("planComment").value.trim();
  if (!text) { toast("warning", "Add a review note", "Write the decision or assumption first."); return; }
  try {
    const plan = await api(`/api/plans/${state.selectedPlan.id}/comments`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text,actor:$("planOwner").value || "Planning team"})});
    state.plans = state.plans.map((row) => row.id === plan.id ? plan : row); state.selectedPlan = plan; $("planComment").value = ""; renderAll(); toast("", "Review note added", plan.name);
  } catch (error) { toast("error", "Note was not added", error.message); }
}
async function revertPlanOverride(overrideId) {
  if (!state.selectedPlan) return;
  const reason = $("planComment").value.trim();
  if (!reason) { toast("warning", "Reason required", "Use the review note field to explain the reversal."); return; }
  try {
    const plan = await api(`/api/plans/${state.selectedPlan.id}/overrides/${overrideId}/revert`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reason,actor:$("planOwner").value || "Planning team"})});
    state.plans = state.plans.map((row) => row.id === plan.id ? plan : row); state.selectedPlan = plan; $("planComment").value = ""; renderAll(); toast("", "Override reversed", "The original entry remains in the audit history.");
  } catch (error) { toast("error", "Override was not reversed", error.message); }
}
async function saveOverride() {
  if (!state.selectedPlan) { toast("warning", "Create or select a plan", "Overrides belong to a traceable plan version."); navigate("plans"); return; }
  try {
    const plan = await api(`/api/plans/${state.selectedPlan.id}/overrides`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({item_id:state.activeItem,period:$("overridePeriod").value,value:Number($("overrideValue").value),reason:$("overrideReason").value,actor:$("planOwner").value || "Planning team"})});
    state.plans = state.plans.map((row) => row.id === plan.id ? plan : row); state.selectedPlan = plan; $("overridePanel").classList.add("hidden"); $("overrideReason").value = ""; toast("", "Override saved", "The statistical baseline remains unchanged.");
  } catch (error) { toast("error", "Override was not saved", error.message); }
}
function saveCurrentView() {
  if (!state.result) return;
  const id = state.activeItem;
  const label = itemLabel(id);
  if (!state.savedViews.some((view) => view.id === id)) state.savedViews.push({id,label});
  localStorage.setItem("demandlab.savedViews", JSON.stringify(state.savedViews));
  renderForecast(); toast("", "View saved", `${label} is available in the view list.`);
}

function bindEvents() {
  document.addEventListener("click", (event) => { const route = event.target.closest("[data-route]")?.dataset.route; if (route) navigate(route); });
  window.addEventListener("popstate", () => navigate(location.hash.slice(1) || "today", {replace:true}));
  $("mobileMenu").addEventListener("click", () => $("sidebar").classList.toggle("open"));
  $("newForecastBtn").addEventListener("click", () => navigate("data"));
  $("loadDemoBtn").addEventListener("click", loadIranDemo);
  $("historyFile").addEventListener("change", () => { state.sourceClassification = "user_provided"; attachFile("history", $("historyFile").files[0]); });
  $("futureFile").addEventListener("change", () => { state.sourceClassification = "user_provided"; attachFile("future", $("futureFile").files[0]); });
  $("operationsFile").addEventListener("change", () => { state.sourceClassification = "user_provided"; attachOperations($("operationsFile").files[0]); });
  ["dateCol","targetCol","itemCol","skuCol","categoryCol","customerCol"].forEach((id) => $(id).addEventListener("change", () => { renderSignals(); updateReadiness(); }));
  $("runForecastBtn").addEventListener("click", () => executeForecast());
  $("forecastItemSelect").addEventListener("change", () => { state.activeItem = $("forecastItemSelect").value; renderForecast(); });
  $("saveViewBtn").addEventListener("click", saveCurrentView);
  $("methodApply").addEventListener("change", () => { $("methodSelection").value = $("methodApply").value; if (state.historyFile) executeForecast({method:$("methodApply").value}); else { navigate("data"); toast("warning", "Source files required", "Reload the source files to run another method."); } });
  $("supplyFilter").addEventListener("change", renderSupply);
  $("applyScenarioBtn").addEventListener("click", () => executeForecast({scenario:true,scenarioName:$("scenarioName").value || "Custom scenario",adjustment:Number($("scenarioAdjustment").value || 0),policy:$("scenarioPolicy").value}));
  $("createPlanBtn").addEventListener("click", createPlan);
  $("addPlanCommentBtn").addEventListener("click", addPlanComment);
  $("refreshPlansBtn").addEventListener("click", async () => { try { state.plans = (await api("/api/plans")).plans || []; renderPlans(); toast("", "Plans refreshed"); } catch (error) { toast("error","Could not refresh plans",error.message); } });
  document.querySelectorAll("[data-plan-status]").forEach((button) => button.addEventListener("click", () => transitionPlan(button.dataset.planStatus)));
  $("addOverrideBtn").addEventListener("click", () => $("overridePanel").classList.toggle("hidden"));
  $("saveOverrideBtn").addEventListener("click", saveOverride);
  $("exportBtn").addEventListener("click", () => { if (state.result?.run_id) window.location.href = `/api/export/${state.result.run_id}/xlsx`; });
  $("newConnectorBtn").addEventListener("click", () => $("connectorForm").classList.remove("hidden"));
  $("cancelConnectorBtn").addEventListener("click", () => $("connectorForm").classList.add("hidden"));
  $("connectorForm").addEventListener("submit", saveConnector);
  $("actualsFile").addEventListener("change", () => { state.actualsFile = $("actualsFile").files[0] || null; $("actualsFileName").textContent = state.actualsFile?.name || "Closed-period actuals"; $("calculateFvaBtn").disabled = !state.result || !state.actualsFile; });
  $("calculateFvaBtn").addEventListener("click", calculateFva);
  $("assistantForm").addEventListener("submit", askAssistant);
  document.querySelectorAll("[data-assistant-question]").forEach((button) => button.addEventListener("click", () => { $("assistantQuestion").value = button.dataset.assistantQuestion; askAssistant(); }));
  window.addEventListener("resize", () => { if (state.route === "forecast") drawChart(activeSeries()); });
}

async function init() {
  try { state.savedViews = JSON.parse(localStorage.getItem("demandlab.savedViews") || "[]"); } catch (_) { state.savedViews = []; }
  bindEvents();
  navigate(location.hash.slice(1) || "today", {replace:true});
  await Promise.all([loadWorkspace(), loadLatestRun()]);
  await loadMonitoring();
}
init();
