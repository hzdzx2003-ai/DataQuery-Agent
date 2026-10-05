import unittest
from capabilities import load_capabilities
from query_plan import validate_query_plan
from plan_view import render_plan
from single_task_evaluation import observed_slots


class ChronologyTests(unittest.TestCase):
    def setUp(self):
        self.cap=load_capabilities()
        self.p={'target':{'kind':'metric','id':'rent_collected'},'filters':[],
                'time':{'kind':'range','start':'2026-01-01','end':'2026-08-31'},
                'group_by':['month'],'order_by':{'by':'month','direction':'asc'}}

    def test_time_sort_not_amount_sort(self):
        r=validate_query_plan(self.cap,self.p)
        self.assertIn('按月份由早到晚',render_plan(self.cap,r))
        self.assertIsNone(observed_slots(r)['order_by'])

    def test_value_rank_and_reverse_time_not_erased(self):
        for by,direction in [('target_value','asc'),('month','desc')]:
            self.p['order_by']={'by':by,'direction':direction}
            r=validate_query_plan(self.cap,self.p)
            self.assertEqual(observed_slots(r)['order_by'],self.p['order_by'])

    def test_no_time_sort_without_group_or_top_n(self):
        self.p['group_by']=[]
        with self.assertRaises(ValueError):validate_query_plan(self.cap,self.p)
        self.p['group_by']=['month'];self.p['order_by']['limit']=3
        with self.assertRaises(ValueError):validate_query_plan(self.cap,self.p)

    def test_point_date_sort(self):
        self.p.update(target={'kind':'metric','id':'leased_area'},time={'kind':'points','dates':['2026-03-31','2026-06-30']},
                      group_by=['point_date'],order_by={'by':'point_date','direction':'asc'})
        self.assertIn('按统计时点由早到晚',render_plan(self.cap,validate_query_plan(self.cap,self.p)))
