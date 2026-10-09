export function scenarioRows(base, scenario, item='__all__') {
  if (scenario.base_run_id !== base.run_id || scenario.unit !== base.unit)
    throw new Error(
      "This scenario does not match the baseline or its quantity unit.",
    );
  if(!base.series[item] || !scenario.series[item]) throw new Error('The selected customer–SKU series is missing from this comparison.');
  const rows = scenario.series[item].forecast;
  const byDate = new Map(rows.map((row) => [row.timestamp.slice(0, 10), row]));
  if (byDate.size !== rows.length)
    throw new Error("The scenario has duplicate forecast periods.");
  return base.series[item].forecast.map((row) => {
    const point = byDate.get(row.timestamp.slice(0, 10));
    const value = Number.isFinite(point?.mean) ? point.mean : null;
    return {
      period: row.timestamp.slice(0, 10),
      baseline: row.mean,
      scenario: value,
      difference: value === null ? null : value - row.mean,
      range:
        Number.isFinite(point?.p10) && Number.isFinite(point?.p90)
          ? [point.p10, point.p90]
          : null,
    };
  });
}

export function factorComparisonScores(base, scenario) {
  if(!['factor_comparison','factor_link'].includes(scenario.scenario?.type))return null;
  if(scenario.metrics?.evidence_policy==='reviewed_what_if'||scenario.scenario?.alignment?.retrospective)
    return {error:'What-if comparison: historical factor release dates are unverified, so past accuracy and forecast ranges are not shown.'};
  if(scenario.base_run_id!==base.run_id || JSON.stringify(base.engine)!==JSON.stringify(scenario.engine) ||
    !base.metrics?.evaluation_signature || base.metrics.evaluation_signature!==scenario.metrics?.evaluation_signature)
    return {error:'Test periods or engine differ. Recalculate a matched comparison.'};
  if(scenario.factor_validation){
    const proof=scenario.factor_validation;
    if(!proof.available||!Number.isFinite(proof.baseline_error_pct)||!Number.isFinite(proof.scenario_error_pct))
      return {error:proof.reason||'There is not enough matched test evidence to compare accuracy.'};
    return {before:proof.baseline_error_pct,after:proof.scenario_error_pct,difference:proof.change_points};
  }
  const before=base.metrics.wape_pct,after=scenario.metrics.wape_pct;
  if(!base.metrics.independent_accuracy_verified||!scenario.metrics.independent_accuracy_verified||!Number.isFinite(before)||!Number.isFinite(after))
    return {error:'There is not enough separate test evidence to compare accuracy.'};
  return {before,after,difference:after-before};
}
