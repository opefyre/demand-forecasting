// A failed read is not evidence of an empty order book.
export function demandLoadState({listing,loading,selected,outlook,error}) {
  if(listing||loading||selected&&!outlook&&!error)return 'loading';
  if(!outlook&&error)return 'unavailable';
  return outlook?'ready':'setup';
}
