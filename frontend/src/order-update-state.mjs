// The existing snapshot API owns validation, revision guards and consumption math.
export function reviewedOrderRequest(initial,inputs,imports,requestId,orderMode='replace'){
  return {inputs:{...inputs,reviewed:true,note:'Customers and order coverage reviewed in the forecast wizard.'},
    imports,request_id:requestId,base_snapshot_id:initial?.base_snapshot_id,order_mode:orderMode,
    ...(initial?.order_refresh_source?{order_refresh_source:initial.order_refresh_source}:{})};
}
