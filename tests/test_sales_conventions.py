from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

import pandas as pd
from persiantools.jdatetime import JalaliDate

from app.sales_conventions import local_today, dates, quantities, normalize_history, month_range, period_start, shift_month
from app.data import prepare_history, build_future_covariates
from app.datasets import DatasetStore
from app.forecast_engine import run_forecast, ModelSpec
from app.sales_demand import demand_outlook, export_demand, import_rows


class SalesConventionsTests(unittest.TestCase):
    def test_tehran_day_changes_before_utc_midnight(self):
        instant=datetime(2026,9,30,21,0,tzinfo=timezone.utc)
        self.assertEqual(local_today('Asia/Tehran',instant),date(2026,10,1))
        self.assertEqual(local_today('UTC',instant),date(2026,9,30))

    def test_digits_and_calendar_are_explicit(self):
        self.assertEqual(dates(pd.Series(['۱۴۰۵/۰۱/۰۱']),'jalali').iloc[0].date(),JalaliDate(1405,1,1).to_gregorian())
        self.assertTrue(dates(pd.Series(['۱۴۰۵/۰۱/۰۱']),'gregorian').isna().all())
        self.assertEqual(quantities(pd.Series(['۱٬۲۳۴٫۵','٠'])).tolist(),[1234.5,0])
        self.assertTrue(quantities(pd.Series(['1,23','NaN',True])).isna().all())

    def test_month_boundaries_and_leap_esfand(self):
        start=JalaliDate(1403,12,1).to_gregorian()
        values=month_range(start,periods=3,basis='jalali')
        self.assertEqual((values[1]-values[0]).days,30)
        self.assertEqual(values[1].date(),JalaliDate(1404,1,1).to_gregorian())
        self.assertEqual(period_start(JalaliDate(1404,1,31).to_gregorian(),'jalali'),values[1])
        self.assertEqual(shift_month(values[1],-1,'jalali'),values[0])

    def history(self):
        return pd.DataFrame({'date':[f'1403-{m:02d}-01' for m in range(1,13)],'qty':[100.]*12,'item':['A']*12})

    def settings(self):
        return dict(date_col='date',target_col='qty',item_col='item',frequency='monthly',
            history_calendar='jalali',history_grain='monthly_totals',month_basis='jalali',
            sales_measure='shipped',returns_policy='reject')

    def test_monthly_total_calendar_mismatch_is_not_silently_relabelled(self):
        with self.assertRaisesRegex(ValueError,'same calendar'):
            normalize_history(self.history(),{**self.settings(),'month_basis':'gregorian'})
        frame=pd.DataFrame({'date':['2026-01-01'],'qty':[10]})
        frame.attrs['wide_forecast_matrix']=True
        with self.assertRaisesRegex(ValueError,'same calendar'):
            normalize_history(frame,{'date_col':'date','target_col':'qty','history_grain':'transactions','month_basis':'jalali'})
        with self.assertRaisesRegex(ValueError,'Monthly totals can only'):
            normalize_history(frame,{'date_col':'date','target_col':'qty','frequency':'weekly'})

    def test_persian_history_future_and_calendar_features(self):
        frame,_=normalize_history(self.history(),self.settings())
        clean,_=prepare_history(frame,date_col='date',target_col='qty',item_col='item',driver_cols=[],frequency='monthly',month_basis='jalali',outlier_strategy='none')
        self.assertEqual(clean.timestamp.iloc[0].date(),JalaliDate(1403,1,1).to_gregorian())
        self.assertEqual(clean.calendar_days_in_period.iloc[0],31)
        self.assertEqual(clean.calendar_days_in_period.iloc[-1],30)
        future,_=build_future_covariates(clean,None,future_date_col=None,future_item_col=None,known_driver_cols=[],frequency='monthly',horizon=3)
        self.assertEqual(future.timestamp.iloc[0].date(),JalaliDate(1404,1,1).to_gregorian())
        self.assertEqual(future.calendar_month.tolist(),[1,2,3])
        with TemporaryDirectory() as root, patch('app.forecast_engine._model_specs',return_value=[ModelSpec('Last observed','last')]):
            result=run_forecast(history=clean,future_covariates=future,known_driver_cols=[],frequency='monthly',horizon=3,profile='fast',runs_dir=Path(root))
            exported=pd.read_csv(Path(root)/result['run_id']/'forecast.csv')
            self.assertEqual(exported.period_label.tolist(),['1404-01','1404-02','1404-03'])
            self.assertEqual(exported.period_end.iloc[0],JalaliDate(1404,1,31).to_gregorian().isoformat())
            receipt=pd.read_excel(Path(root)/result['run_id']/'forecast_package.xlsx',sheet_name='Sales meaning')
            self.assertIn('sales_measure',receipt.setting.tolist())
        self.assertEqual(result['series']['A']['forecast'][0]['timestamp'],JalaliDate(1404,1,1).to_gregorian().isoformat())

    def test_returns_are_reviewed_and_reconciled_not_clipped(self):
        f=pd.DataFrame({'date':list(pd.date_range('2024-01-01',periods=12,freq='MS'))+[pd.Timestamp('2024-01-02')],'qty':[10.]*12+[-3.]})
        settings=dict(date_col='date',target_col='qty',sales_measure='shipped',returns_policy='net_returns')
        normalized,warnings=normalize_history(f,settings)
        clean,_=prepare_history(normalized,date_col='date',target_col='qty',item_col=None,driver_cols=[],frequency='monthly',outlier_strategy='none')
        self.assertEqual(clean.target.iloc[0],7)
        self.assertEqual(clean.target.sum(),117)
        self.assertEqual(normalized.attrs['sales_conventions']['return_quantity'],3)
        self.assertEqual(f.qty.iloc[-1],-3)
        f.loc[len(f)-1,'qty']=-11
        normalized,_=normalize_history(f,settings)
        with self.assertRaisesRegex(ValueError,'Returns exceed'):
            prepare_history(normalized,date_col='date',target_col='qty',item_col=None,driver_cols=[],frequency='monthly')

    def test_source_inspection_and_saved_receipt(self):
        with TemporaryDirectory() as root:
            store=DatasetStore(Path(root));source=store.upload('persian.csv',self.history().to_csv(index=False).encode(),'history')
            review=store.inspect({'history':source['id']},self.settings())
            self.assertEqual(review['sales_conventions']['forecast_month_basis'],'jalali')
            self.assertEqual(review['summary']['total_demand'],1200)
            self.assertEqual(store.source(source['id'])[1],self.history().to_csv(index=False).encode())

    def test_persian_orders_use_exact_month_and_export_boundaries(self):
        start=JalaliDate(1405,7,1).to_gregorian().isoformat()
        run={'run_id':'A','unit':'tonnes','source_classification':'synthetic_sample','run_settings':{'frequency':'monthly','calendar_profile':{'month_basis':'jalali'}},'metadata':{'A':{'customer':'C','sku':'S'}},'series':{'A':{'forecast':[{'timestamp':start,'mean':10}]}}}
        payload={'name':'test','run_id':'A','as_of':start,'valid_until':'2026-12-01','classification':'synthetic_sample','order_feed':'complete_snapshot','reviewed':True,'note':'Checked orders','customers':[{'customer':'C','sku':'S','unit':'tonnes','series_id':'A'}],'orders':[{'reference':'O','customer':'C','sku':'S','unit':'tonnes','due_date':JalaliDate(1405,7,20).to_gregorian().isoformat(),'ordered':15,'status':'confirmed'}]}
        outlook=demand_outlook(payload,run,today=date(2026,10,3))
        self.assertEqual(outlook['rows'][0]['period_label'],'1405-07')
        self.assertEqual(outlook['rows'][0]['booked'],15)
        self.assertEqual(outlook['rows'][0]['remaining'],0)
        self.assertEqual(outlook['rows'][0]['period_end'],JalaliDate(1405,7,30).to_gregorian().isoformat())
        data,_=export_demand(outlook,'combined_demand','json')
        self.assertIn(b'1405-07',data)

    def test_order_import_persian_numbers_dates_receipt(self):
        with TemporaryDirectory() as root:
            store=DatasetStore(Path(root))
            raw='reference,customer,sku,unit,due_date,ordered,status\nO,C,S,tonnes,۱۴۰۵/۰۷/۱۰,۱۲٫۵,confirmed\n'.encode()
            source=store.upload('orders.csv',raw,'sales_orders')
            config={'source_id':source['id'],'calendar':'jalali','mapping':dict(zip(['reference','customer','sku','unit','due_date','ordered','status'],list('ABCDEFG')))}
            rows,proof=import_rows(store,'orders',config)
            self.assertEqual(rows[0]['ordered'],'12.5')
            self.assertEqual(rows[0]['due_date'],JalaliDate(1405,7,10).to_gregorian().isoformat())
            self.assertEqual(proof['calendar'],'jalali')

    def test_saved_client_workbook_does_not_lose_monthly_grain_when_canonicalized(self):
        import asyncio
        import json
        import app.main as main
        from fastapi import HTTPException
        frame=pd.DataFrame({'date':['2026-01-01'],'qty':[10]})
        frame.attrs['wide_forecast_matrix']=True
        settings={'date_col':'date','target_col':'qty','month_basis':'jalali','history_grain':'transactions'}
        dataset={'id':'demo','name':'demo','classification':'synthetic_sample','settings':settings,'sources':{'history':'source'}}
        store=MagicMock();store.get.return_value=dataset;store.source.return_value=({'name':'client.xlsx','sheet':'Actuals'},b'unchanged')
        runner=AsyncMock(side_effect=ValueError('Captured inputs'))
        with patch.object(main,'DATASET_STORE',store),patch.object(main,'read_table',return_value=frame),patch.object(main,'run',runner):
            with self.assertRaises(HTTPException):asyncio.run(main.run_saved(main.SavedRunConfig(dataset_id='demo')))
        declared=json.loads(runner.call_args.kwargs['sales_conventions_json'])
        self.assertEqual(declared['history_grain'],'monthly_totals')
        self.assertEqual(declared['history_calendar'],'gregorian')
        self.assertEqual(declared['month_basis'],'jalali')
        self.assertEqual(settings['history_grain'],'transactions')


if __name__=='__main__':unittest.main()
