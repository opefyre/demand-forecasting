"""Three bounded, genuine AI queries about fictional demo data; no actions approved."""
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'outputs/tehran-sales-demo/manifest.json'


def main():
    manifest = json.loads(MANIFEST.read_text())
    run_id = manifest['runs']['gregorian:recommended']
    cases = [('Monthly sales outlook', 'Show the combined demand for October, November and December 2026, in tonnes. Separate confirmed outstanding orders from remaining forecast. Use saved figures only. Keep it brief. Do not create or approve anything.'),
             ('Customer order coverage', 'Compare Mehr Packaging and Aftab Printing for November 2026. Show confirmed outstanding orders, calculated demand still to come, and total demand. Does having no orders mean no expected sales? Use saved data only; keep it brief. Do not modify anything.'),
             ('Persian forecast summary', 'پیش‌بینی فروش مشتری Simin Foods برای سه ماه اکتبر، نوامبر و دسامبر ۲۰۲۶ چقدر است؟ سفارش‌های قطعی و تقاضای باقی‌مانده را جداگانه نشان بده. فقط از اعداد ذخیره‌شده استفاده کن. کوتاه و فارسی پاسخ بده. هیچ تغییری انجام نده.')]
    receipts = manifest.setdefault('assistant_examples', [])
    with httpx.Client(base_url='http://127.0.0.1:8010', timeout=170) as client:
        status = client.get('/api/ai/status').raise_for_status().json()
        assert status['ready'], 'Existing AI setup is not ready; no simulated answers will be added.'
        snapshot = client.get(f'/api/sales/runs/{run_id}/inputs').raise_for_status().json()['snapshots'][0]['id']
        for title, question in cases:
            if any(r['title']==title for r in receipts): continue
            response = client.post('/api/ai/chat', json=dict(question=question, run_id=run_id,
                snapshot_id=snapshot, consent=True, provider_id=status['consent_id'], mode='query'))
            response.raise_for_status()
            result = response.json()
            assert result.get('answer') and not result.get('actions'), 'Query must answer without an action.'
            client.post(f"/api/ai/conversations/{result['id']}/rename", json={'title':title}).raise_for_status()
            receipts.append(dict(title=title, turn_id=result['id'], run_id=run_id, snapshot_id=snapshot,
                role=result.get('role'), genuine_provider_answer=True))
            current = json.loads(MANIFEST.read_text())
            current['assistant_examples'] = receipts
            MANIFEST.write_text(json.dumps(current, ensure_ascii=False, indent=2))
            print(json.dumps(receipts[-1]), flush=True)


if __name__ == '__main__':
    main()
