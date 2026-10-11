// The existing snapshot API owns validation, revision guards and consumption math.
export function reviewedOrderRequest(initial,inputs,imports,requestId,orderMode='replace'){
  return {inputs:{...inputs,reviewed:true,note:'Customers and order coverage reviewed in the forecast wizard.'},
    imports,request_id:requestId,base_snapshot_id:initial?.base_snapshot_id,order_mode:orderMode,
    ...(initial?.order_refresh_source?{order_refresh_source:initial.order_refresh_source}:{})};
}

export async function saveForecastOrderReview(api,path,datasetId,version,payload,review,onVersion){
  const {as_of,valid_until,order_feed,orders}=review.inputs;
  const book=await api('/api/order-books/'+datasetId,{version,as_of,valid_until,order_feed,orders},'PUT');
  onVersion?.(book.version);
  const saved=await api(path,{...payload,review_token:review.review_token});
  return {saved,version:book.version};
}

// Exception warnings require a visible review before either store is changed.
export async function checkForecastOrderReview(api,path,datasetId,version,payload,onVersion){
  const review=await api(path+'/preview',payload);
  if(review.warnings?.length)return {review,payload};
  return saveForecastOrderReview(api,path,datasetId,version,payload,review,onVersion);
}
