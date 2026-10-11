const finished=new Set(['succeeded','failed','interrupted','cancelled']);
export const forecastFinished=job=>finished.has(job.state);

// A retry replaces the previous attempt; do not offer a second retry of it.
export function currentForecastJobs(jobs){
  const replaced=new Set(jobs.map(job=>job.retry_of).filter(Boolean));
  return jobs.filter(job=>!replaced.has(job.id));
}

// Read each method independently. One unavailable job must not hide the others.
export async function readForecastProgress(jobs,api){
  const replies=await Promise.allSettled(jobs.map(job=>forecastFinished(job)?job:
    api('/api/jobs/'+job.id).then(value=>({...value,method:job.method}))));
  return {jobs:replies.map((reply,index)=>reply.status==='fulfilled'?reply.value:jobs[index]),
    error:replies.find(reply=>reply.status==='rejected')?.reason||null};
}

export async function readForecastSummaries(jobs,customer,api){
  const replies=await Promise.allSettled(jobs.filter(job=>job.state==='succeeded'&&job.run_id).map(async job=>{
    const run=await api('/api/runs/'+job.run_id);
    if(customer&&run.sales_input_snapshot_id){
      const outlook=await api('/api/sales/inputs/'+run.sales_input_snapshot_id+'/outlook');
      const rows=outlook.rows.filter(row=>row.customer===customer);
      return [job.run_id,{total:rows.length&&rows.every(row=>row.total!=null)?rows.reduce((sum,row)=>sum+row.total,0):null,unit:run.unit}];
    }
    return [job.run_id,run.demand_summary||{total:null,unit:run.unit}];
  }));
  return {summaries:Object.fromEntries(replies.filter(reply=>reply.status==='fulfilled').map(reply=>reply.value)),
    error:replies.find(reply=>reply.status==='rejected')?.reason||null};
}
