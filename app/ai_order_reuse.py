"""Assistant proposals around existing order-coverage review, never order edits."""
from .order_reuse import compatible, preview_reuse


class AssistantOrderReuse:
    def __init__(self, store, load_run, list_runs, target):
        self.store, self.load_run, self.list_runs, self.target = store, load_run, list_runs, target

    def choices(self):
        rows=[]
        for row in self.list_runs()['runs']:
            if compatible(self.load_run(row['run_id']),self.target):
                versions=self.store.list(row['run_id'])
                if versions:
                    source=versions[0]
                    rows.append({'snapshot_id':source['id'],'name':row['name'],
                        'as_of':source['inputs']['as_of'],'valid_until':source['inputs']['valid_until']})
        return {'sources':rows[:50],'total_sources':len(rows),'truncated':len(rows)>50}

    def preview(self, snapshot_id):
        if snapshot_id not in {s['snapshot_id'] for s in self.choices()['sources']}:
            raise ValueError('Choose an exact compatible order version returned by inspect_saved_orders. Do not guess.')
        return preview_reuse(self.store,self.load_run,self.target['run_id'],snapshot_id)[0]

    def proposal(self, snapshot_id):
        report=self.preview(snapshot_id)
        if not report['can_save']:
            raise ValueError('Orders are expired or demand is incomplete. Review current orders before saving a draft.')
        return {'kind':'order_reuse','target_run_id':self.target['run_id'],
            'snapshot_id':snapshot_id,'review_token':report['review_token'],'preview':report,
            'message':'All customers and SKUs. User must confirm full order-book coverage; no orders are edited.'}
