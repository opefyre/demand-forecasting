"""Request-bound report and personal-context access. No shared-data fallback."""
import json
from types import SimpleNamespace
from urllib.parse import urlencode
from fastapi import HTTPException
from .platform_identity import principal
from .demand_releases import identity
from .sales_demand import demand_outlook
from .ai_workspace import install_ai_routes


def personal_owner(who):
    # A company integration key is not a person's private conversation history.
    if who.get('key_kind') == 'company' or str(who.get('subject','')).startswith(('company-key:','service:')):
        raise HTTPException(403, 'Use personal access for conversations and saved views.')
    return json.dumps([who['company_id'], who['issuer'], who['subject']])


class ReportAccess:
    def __init__(self, workspace, who):
        self.ws, self.who = workspace, who
        self.drafts = 'drafts:read' in who['permissions']

    def approved(self, run_id, snapshot_id=None):
        for row in self.ws.releases.list(run_id):
            if row['state'] != 'approved' or (snapshot_id and row['snapshot_id'] != snapshot_id):
                continue
            record = self.ws.releases.detail(row['id'], identity(self.who), self.who['role'])
            if record['can_export']:
                return record
        raise HTTPException(404, 'Approved report not found.')

    def run(self, key):
        if 'reports:read' not in self.who['permissions']:
            raise HTTPException(403, 'Your access does not allow this action.')
        if not self.drafts:
            self.approved(key)
        try:
            value = dict(self.ws.load_run(key))
            value.pop('job_owner', None)
            return value
        except ValueError:
            raise HTTPException(404, 'Forecast not found.') from None

    def snapshot(self, key):
        if 'reports:read' not in self.who['permissions']:
            raise HTTPException(403, 'Your access does not allow this action.')
        try:
            value = self.ws.sales.get(key)
            run_id = value['inputs']['run_id']
            if not self.drafts:
                self.approved(run_id, key)
            return value
        except ValueError:
            raise HTTPException(404, 'Order review not found.') from None

    def outlook(self, key):
        saved = self.snapshot(key)
        run = self.ws.load_run(saved['inputs']['run_id'])
        from .sales_api import run_hash
        proof = next((e['run_sha256'] for e in saved['evidence'] if 'run_sha256' in e), None)
        if proof != run_hash(run):
            raise HTTPException(409, 'Forecast changed. Review its orders again.')
        value = {**demand_outlook(saved['inputs'], run), 'snapshot_id':key,
                 'created_at':saved['created_at'], 'evidence':saved['evidence']}
        return value

    def chat_context(self, turn):
        if turn.get('dataset_id') and 'inputs:read' not in self.who['permissions']:
            raise HTTPException(404, 'Conversation context is unavailable.')
        if turn.get('run_id'):
            self.run(turn['run_id'])
            if not self.drafts and not turn.get('snapshot_id'):
                # A previous draft-only conversation must not become visible on demotion.
                raise HTTPException(404, 'Conversation context is unavailable.')
        if turn.get('snapshot_id'):
            self.snapshot(turn['snapshot_id'])


class PersonalJournal:
    """Recheck role/report access on saved text as well as on new tool requests."""
    def __init__(self, journal, access):
        self.journal, self.access, self.path = journal, access, journal.path

    def _read(self, key, actor):
        created, turn = self.journal._read(key, actor)
        self.access.chat_context(turn)
        return created, turn

    def get(self, key, actor):
        self._read(key, actor)
        return self.journal.get(key, actor)

    def conversation(self, *args, **kwargs):
        rows = self.journal.conversation(*args, **kwargs)
        for row in rows:
            self.access.chat_context(row)
        return rows

    def list_chats(self, actor, offset=0, limit=50, **kwargs):
        # Filter before pagination so inaccessible titles are not leaked.
        visible, position = [], 0
        while True:
            page = self.journal.list_chats(actor, position, 100, **kwargs)
            for row in page['chats']:
                try:
                    self._read(row['head_id'], actor)
                except (ValueError, HTTPException):
                    continue
                visible.append(row)
            if page['next_offset'] is None:
                break
            position = page['next_offset']
        return {'chats':visible[offset:offset+limit],
                'next_offset':offset+limit if len(visible)>offset+limit else None}

    def rename(self, key, actor, *args):
        self._read(key, actor)
        return self.journal.rename(key, actor, *args)

    def update_chat(self, key, actor, operation):
        self._read(key, actor)
        return self.journal.update_chat(key, actor, operation)

    def chat_state(self, key, actor):
        self._read(key, actor)
        return self.journal.chat_state(key, actor)

    def put(self, actor, payload):
        self.access.chat_context(payload)
        return self.journal.put(actor, payload)

    def record_result(self, key, actor, index, result):
        self._read(key, actor)
        return self.journal.record_result(key, actor, index, result)


def install_company_assistant(api, workspaces, dispatcher=None):
    if dispatcher is None:
        from .company_jobs import dispatch
        dispatcher=dispatch
    def owner(request):
        return personal_owner(principal(request, 'chats:own'))

    def services(request, operation):
        who = principal(request, 'ai:query')
        principal(request, 'chats:own')
        personal_owner(who)
        if workspaces is None:
            raise HTTPException(503, 'Company storage is not configured.')
        ws = workspaces.for_principal(who)
        access = ReportAccess(ws, who)
        can_inputs = 'inputs:read' in who['permissions']
        scopes=set(who['permissions'])
        can_orders={'reports:read','drafts:read','orders:read'}<=scopes
        can_factors={'reports:read','drafts:read','inputs:read','factors:read'}<=scopes
        can_profiles=can_factors and 'customers:read' in scopes
        advanced={'ai:actions','reports:read','drafts:read','inputs:read','inputs:write',
                  'factors:read','factors:write','forecasts:run'}
        tools = {'inspect_forecast', 'compare_methods'}
        if can_inputs:
            tools |= {'inspect_inputs','inspect_input_formatting'}
        if {'ai:actions','inputs:write'} <= set(who['permissions']):
            tools |= {'prepare_input_mapping','prepare_input_corrections','prepare_history_refresh'}
        if {'ai:actions','forecasts:run','inputs:write','orders:read','factors:read'} <= set(who['permissions']):
            tools.add('prepare_forecast')
        if 'reports:export' in who['permissions']:
            tools.add('prepare_export')
        if can_orders:
            tools|={'inspect_scenarios','preview_order_scenario','inspect_saved_orders','preview_saved_orders'}
            if {'ai:actions','orders:write'}<=scopes:
                tools|={'prepare_order_import','prepare_order_scenario','prepare_saved_orders'}
        if can_factors:
            tools|={'inspect_factor_sources','preview_factor_scenario','inspect_factor_batch','preview_factor_batch'}
            if advanced<=scopes:
                tools|={'prepare_factor_scenario','prepare_factor_batch','prepare_customer_factor_batch'}
        if can_profiles:
            tools|={'inspect_factor_profiles','preview_profile_sources'}
            if advanced<=scopes:tools.add('prepare_profile_sources')
        if advanced|{'orders:read'}<=scopes:tools.add('prepare_monthly_update')
        if operation == 'import_mapping':
            principal(request,'ai:actions'); principal(request,'inputs:write')

        def authorize_action(action):
            kind = action.get('kind')
            if kind == 'export':
                principal(request,'reports:export')
                access.snapshot(action['snapshot_id'])
                return
            required = {'forecast':{'ai:actions','forecasts:run','inputs:write','orders:read','factors:read'},
                        'input_mapping':{'ai:actions','inputs:write'},
                        'input_correction':{'ai:actions','inputs:write'},
                        'history_refresh':{'ai:actions','inputs:write'}}
            required.update({k:advanced for k in ('factor_scenario','factor_batch','factor_batch_review')})
            required['factor_preparation']=advanced|{'customers:read'}
            required['monthly_update']=advanced|{'orders:read'}
            required.update({k:{'ai:actions','reports:read','drafts:read','orders:read','orders:write'}
                             for k in ('order_import','order_scenario','order_reuse')})
            if kind not in required:
                raise HTTPException(403, 'This workflow is not available in company access yet.')
            for scope in required[kind]: principal(request,scope)

        def export_url(action):
            saved = access.snapshot(action['snapshot_id'])
            params = urlencode({'mode':action['mode'],'kind':action['format']})
            if access.drafts:
                return f'/api/v1/order-snapshots/{saved["id"]}/export?{params}'
            record = access.approved(saved['inputs']['run_id'], saved['id'])
            if action['mode'] != record['contract']['mode']:
                raise HTTPException(403, 'Use the approved report export policy.')
            return f'/api/v1/releases/{record["id"]}/export?kind={action["format"]}'

        def load_run(key):
            access.run(key)
            # Internal review hashes include the exact persisted job evidence.
            return ws.load_run(key)
        def submit(*args):
            from .company_workflows import submit_draft
            for scope in advanced:principal(request,scope)
            return submit_draft(ws,dispatcher,*args)
        return SimpleNamespace(journal=PersonalJournal(ws.journal,access),ledger=ws.ai_ledger,
            load_run=load_run,get_outlook=access.outlook,datasets=ws.datasets if can_inputs else None,
            sales_store=ws.sales if can_orders else None,
            list_runs=(lambda:{'runs':[dict(r,name=r.get('scenario_name') or r.get('dataset_name','Forecast')) for r in ws.list_runs()]}) if can_orders else None,
            factors=ws.factors if can_factors else None,live=ws.live_sources if can_factors else None,
            profiles=ws.profiles if can_profiles else None,job_status=ws.jobs.get if can_factors else None,
            submit=submit if advanced<=scopes else None,allowed_tools=tools,authorize_action=authorize_action,export_url=export_url)

    install_ai_routes(api,None,None,None,None,None,prefix='/ai',services=services,actor_provider=owner)
