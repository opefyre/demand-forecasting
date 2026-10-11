// A slow workspace refresh must not reopen a forecast after the user leaves chat.
export async function openAssistantForecast(result,{refresh,isCurrent,onNewForecast}){
  if(!isCurrent())return false;
  await refresh?.();
  if(!isCurrent())return false;
  onNewForecast?.(result.dataset_id,result.method,result.customer);
  return true;
}
