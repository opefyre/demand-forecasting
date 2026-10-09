"""Clarify delivered versus outstanding quantities in the genuine Persian demo chat."""
import json
import math
import re
import httpx
from scripts.prepare_tehran_demo import MANIFEST, write


def populate():
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('persian_answer_verified'): return
    example = next(e for e in manifest['assistant_examples'] if e['title']=='Persian forecast summary')
    with httpx.Client(base_url='http://127.0.0.1:8010', timeout=170) as client:
        status = client.get('/api/ai/status').raise_for_status().json()
        result = client.post('/api/ai/chat',json=dict(run_id=example['run_id'],snapshot_id=example['snapshot_id'],
            previous_turn_id=example['turn_id'],consent=True,provider_id=status['consent_id'],mode='query',
            question='برای همان مشتری و همان سه ماه، لطفاً مانده سفارش قطعی، مقدار تحویل‌شده، تقاضای اضافی هنوز سفارش‌نشده و کل تقاضای ماه را جداگانه در یک جدول نشان بده. ارقام تحویل‌شده را دوباره از مانده سفارش کم نکن. کوتاه و فارسی پاسخ بده و چیزی را تغییر نده.')).raise_for_status().json()
        from app import main
        from app.sales_demand import demand_outlook
        from app.ai_workspace import forecast_month_totals
        run = main._load_run(example['run_id']); snap = main.SALES_STORE.get(example['snapshot_id'])
        totals = forecast_month_totals([r for r in demand_outlook(snap['inputs'],run)['rows'] if r['customer']=='Simin Foods'],
            ('booked','fulfilled','remaining','total'))[:3]
        answer = result['answer']
        for label, month in zip(('اکتبر','نوامبر','دسامبر'),totals):
            line = next(line for line in answer.splitlines() if label in line)
            numbers = [float(value.replace(',','')) for value in re.findall(r'\d[\d,]*\.\d+|\b\d+\b',line)]
            assert all(any(math.isclose(month[field], value, abs_tol=.005) for value in numbers)
                for field in ('booked','fulfilled','remaining','total')), 'Persian answer does not match computed quantities.'
        assert not result.get('actions')
        example['head_id'] = result['id']
        manifest['persian_answer_verified'] = True
        write(MANIFEST,manifest)
        print(json.dumps({'verified_months':3,'verified_numeric_totals':12}),flush=True)


if __name__=='__main__':
    populate()
