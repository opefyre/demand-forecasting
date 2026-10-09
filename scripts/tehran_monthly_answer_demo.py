"""Replace the archived failed lookup with a genuine, verified monthly demo answer."""
import json
import math
import re
from scripts.prepare_tehran_demo import MANIFEST, write
import httpx


def populate():
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('monthly_answer_verified'): return
    old = next(r for r in manifest['assistant_examples'] if r['title']=='Monthly sales outlook')
    with httpx.Client(base_url='http://127.0.0.1:8010', timeout=170) as client:
        status = client.get('/api/ai/status').raise_for_status().json()
        payload = dict(run_id=old['run_id'], snapshot_id=old['snapshot_id'], consent=True,
            provider_id=status['consent_id'], mode='query',
            question='Using the orders already applied to this forecast, show combined demand for October, November and December 2026 in tonnes. Separate confirmed outstanding orders from calculated demand still to come. Keep it brief; do not change anything.')
        from app.ai_workspace import AIJournal
        journal = AIJournal(MANIFEST.parents[2] / 'data/ai-workspace.sqlite3')
        existing = []
        for chat in journal.list_chats('local')['chats']:
            turn = journal.get(chat['head_id'], 'local')
            if all(turn.get(field)==payload.get(field) for field in ('question','run_id','snapshot_id')):
                existing.append({**turn, 'id':chat['head_id']})
        result = existing[0] if existing else client.post('/api/ai/chat', json=payload).raise_for_status().json()
        assert result.get('answer') and not result.get('actions')
        answer = result['answer']
        assert 'October' in answer and 'November' in answer and 'December' in answer
        from app import main
        from app.ai_workspace import forecast_month_totals
        from app.sales_demand import demand_outlook
        run = main._load_run(old['run_id'])
        snap = main.SALES_STORE.get(old['snapshot_id'])
        totals = forecast_month_totals(demand_outlook(snap['inputs'], run)['rows'], ('booked','remaining','total'))[:3]
        for label, month in zip(('October','November','December'), totals):
            line = next(line for line in answer.splitlines() if label in line)
            numbers = [float(value.replace(',','')) for value in re.findall(r'\d[\d,]*\.\d+',line)]
            # The model may format 3 or 6 decimals. Validate the actual values,
            # not one arbitrary display precision, while allowing no math changes.
            assert len(numbers)==3 and all(any(math.isclose(month[field], value, abs_tol=.0005) for value in numbers)
                for field in ('booked','remaining','total')), f'Incorrect complete totals for {label}.'
        client.post(f"/api/ai/conversations/{result['id']}/rename", json={'title':old['title']}).raise_for_status()
        client.post(f"/api/ai/conversations/{old['turn_id']}/manage", json={'operation':'archive'}).raise_for_status()
        # Archive other unsuccessful copies of this exact demo query, not unrelated chats.
        for chat in journal.list_chats('local')['chats']:
            if chat['head_id'] in (result['id'], old['turn_id']): continue
            turn = journal.get(chat['head_id'], 'local')
            if all(turn.get(field)==payload.get(field) for field in ('question','run_id','snapshot_id')):
                client.post(f"/api/ai/conversations/{chat['head_id']}/manage", json={'operation':'archive'}).raise_for_status()
        replacement = {**old, 'turn_id':result['id'], 'verified_monthly_totals':totals}
        manifest['assistant_examples'] = [replacement if r['title']==old['title'] else r for r in manifest['assistant_examples']]
        manifest['monthly_answer_verified'] = True
        manifest['archived_demo_lookup'] = old['turn_id']
        write(MANIFEST, manifest)
        print(json.dumps({'verified_months':3,'verified_numeric_totals':9,'turn_id':result['id']}), flush=True)


if __name__ == '__main__':
    populate()
