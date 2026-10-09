// Only an opaque server turn ID lives in browser storage, never chat contents.
export const chatKey=(run,snapshot,dataset)=>'demandlab.chat.'+JSON.stringify(dataset?[null,null,dataset]:[run||null,snapshot||null]);
export function readChatHead(storage,key){try{return storage.getItem(key)||null;}catch{return null;}}
export function writeChatHead(storage,key,id){try{if(id)storage.setItem(key,id);else storage.removeItem(key);}catch{/* Memory still works when storage is unavailable. */}}
export function chatPayload(question,runId,snapshot,turns,datasetId){
  return {question,run_id:runId||null,snapshot_id:snapshot||null,...(datasetId?{dataset_id:datasetId}:{}),previous_turn_id:turns.at(-1)?.id||null,consent:true,mode:'auto'};
}
export function readInputChoice(storage,runId,datasets){
  try{
    const saved=JSON.parse(storage.getItem('demandlab.assistantInputs')||'null');
    return saved?.run_id===(runId||null)&&datasets.some(d=>d.id===saved.dataset_id&&!d.scenario_provenance&&!d.sources?.operations)?'dataset:'+saved.dataset_id:'';
  }catch{return '';}
}
export function writeInputChoice(storage,runId,datasetId){
  try{
    if(datasetId)storage.setItem('demandlab.assistantInputs',JSON.stringify({run_id:runId||null,dataset_id:datasetId}));
    else storage.removeItem('demandlab.assistantInputs');
  }catch{/* Only opaque context IDs are persisted; chat remains usable without storage. */}
}
