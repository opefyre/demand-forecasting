import json
import unittest

import pandas as pd

from app.sales_conventions import normalize_history
from app.sales_groups import PAIR_COLUMN, customer_product_series, customer_product_future, series_column


class SalesGroupingTests(unittest.TestCase):
    def settings(self, **overrides):
        return dict(date_col='date',target_col='quantity',customer_col='customer',sku_col='sku',
                    series_mode='customer_product',**overrides)

    def test_exact_pairs_preserve_identifiers_quantity_and_source(self):
        raw=pd.DataFrame([{'customer':'0001','sku':'001','quantity':10},
                          {'customer':'0002','sku':'001','quantity':20},
                          {'customer':'A|B','sku':'C','quantity':3},
                          {'customer':'A','sku':'B|C','quantity':4}])
        before=raw.copy(deep=True)
        result=customer_product_series(raw,self.settings())
        self.assertEqual(result[PAIR_COLUMN].nunique(),4)
        self.assertEqual(json.loads(result[PAIR_COLUMN].iloc[0]),['0001','001'])
        self.assertEqual(result.quantity.sum(),37)
        pd.testing.assert_frame_equal(raw,before)
        self.assertEqual(series_column(self.settings()),PAIR_COLUMN)

    def test_reviewed_aliases_precede_group_keys(self):
        raw=pd.DataFrame(dict(date=['2025-01-01']*2,customer=['Alias','Customer'],sku=['001']*2,quantity=[10,20]))
        out,_=normalize_history(raw,self.settings(customer_aliases={'Alias':'Customer'}))
        self.assertEqual(out[PAIR_COLUMN].nunique(),1)
        self.assertEqual(out.quantity.sum(),30)

    def test_missing_misassigned_and_tampered_groups_stop(self):
        frame=pd.DataFrame(dict(customer=['A'],sku=['001'],quantity=[10],date=['2025-01-01']))
        for change in ({'customer_col':'missing'},{'customer_col':'sku'},{'sku_col':'quantity'}):
            with self.assertRaises(ValueError):
                customer_product_series(frame,{**self.settings(),**change})
        with self.assertRaisesRegex(ValueError,'no customer'):
            customer_product_series(frame.assign(customer=None),self.settings())
        with self.assertRaisesRegex(ValueError,'keys do not match'):
            customer_product_series(frame.assign(**{PAIR_COLUMN:'wrong'}),self.settings())
        valid=customer_product_series(frame,self.settings())
        pd.testing.assert_frame_equal(customer_product_series(valid,self.settings()),valid)

    def test_legacy_group_never_selects_the_last_of_multiple_customers(self):
        raw=pd.DataFrame(dict(date=['2025-01-01']*2,customer=['A','B'],sku=['001']*2,quantity=[10,20]))
        with self.assertRaisesRegex(ValueError,'different customer'):
            normalize_history(raw,{**self.settings(),'series_mode':'column','item_col':'sku'})
        with self.assertRaisesRegex(ValueError,'grouping'):
            series_column({'series_mode':'guess'})

    def test_shared_and_scoped_future_factors(self):
        history=customer_product_series(pd.DataFrame(dict(customer=['A','B'],sku=['001']*2,group=['a','b'])),self.settings(item_col='group'))
        future=pd.DataFrame(dict(customer=['B','A'],sku=['001']*2,price=[5,7]))
        out,item=customer_product_future(future,history,self.settings())
        self.assertEqual(item,PAIR_COLUMN)
        self.assertEqual(json.loads(out[item].iloc[0]),['B','001'])
        shared=pd.DataFrame({'price':[5]})
        self.assertIs(customer_product_future(shared,history,self.settings())[0],shared)
        mapped,item=customer_product_future(pd.DataFrame(dict(group=['b'],price=[8])),history,
            self.settings(item_col='group',future_item_col='group'))
        self.assertEqual(json.loads(mapped[item].iloc[0]),['B','001'])
        canonical=pd.DataFrame(dict(item_id=history[PAIR_COLUMN],price=[5,7]))
        out,item=customer_product_future(canonical,history,self.settings(future_item_col='item_id'))
        pd.testing.assert_frame_equal(out,canonical)
        with self.assertRaisesRegex(ValueError,'multiple customers'):
            customer_product_future(pd.DataFrame(dict(sku=['001'],price=[8])),history,
                self.settings(item_col='sku',future_item_col='sku'))


if __name__=='__main__':
    unittest.main()
