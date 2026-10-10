import { DurableObject, WorkerEntrypoint } from 'cloudflare:workers';
import { CloudEngineController } from './engine-lifecycle.mjs';
const closed=()=>new Response(null,{status:404,headers:{'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow'}});
export class ForecastEngine extends DurableObject {
  constructor(ctx,env) { super(ctx,env);this.controller=new CloudEngineController(ctx,env); }
  execute(job) { return this.controller.execute(job); }
  alarm() { return this.controller.alarm(); }
  status() { return this.controller.status(); }
  fetch() { return closed(); }
}
export class ForecastRunner extends WorkerEntrypoint {
  engine() { return this.env.ENGINE.get(this.env.ENGINE.idFromName('forecast-engine-v1')); }
  execute(job) { return this.engine().execute(job); }
  status() { return this.engine().status(); }
}
export default {fetch:closed};
