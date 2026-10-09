export function workflowState({ run, datasets = [], runs = [], hasDraft = false }) {
  const classification = record => record.source_classification || datasets.find(d => d.id === record.dataset_id)?.classification;
  const realRuns = runs.filter(r => !r.scenario_name && classification(r) === 'user_provided');
  const sampleRuns = runs.filter(r => !r.scenario_name && classification(r) === 'synthetic_sample');
  const realData = datasets.filter(d => d.classification === 'user_provided');
  const current = run?.source_classification === 'user_provided'
    ? realRuns.find(r => r.run_id === run.run_id) || { ...run, name: run.dataset_name }
    : realRuns[0];
  const sample = sampleRuns.find(r => r.run_id === run?.run_id) || sampleRuns[0];
  const stage = hasDraft ? 'import' : current ? 'review' : realData.length ? 'calculate' : 'start';
  return { realRuns, realData, current, sample, stage };
}

export function pendingImport(raw) {
  try {
    const draft = JSON.parse(raw);
    return draft?.sources?.history ? {exists:true,sample:draft.classification==='synthetic_sample'} : {exists:false,sample:false};
  } catch { return {exists:false,sample:false}; }
}
