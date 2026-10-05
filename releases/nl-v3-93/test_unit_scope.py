import unittest
from capabilities import load_capabilities
from query_plan import validate_query_plan
from plan_view import render_plan


class UnitScopeTests(unittest.TestCase):
    def setUp(self):
        self.cap=load_capabilities()
        self.plan={'target':{'kind':'metric','id':'occupancy_rate'},
                   'filters':[{'dimension':'unit_type','operator':'in','values':['office']},
                              {'dimension':'floor','operator':'in','values':['2']}],
                   'time':{'kind':'point','date':'2025-12-31'},
                   'group_by':['project','floor'], 'order_by':None}

    def test_three_point_metrics_accept_unit_scope(self):
        for metric in ('leased_area','occupancy_rate','avg_monthly_rent_per_sqm'):
            self.plan['target']['id']=metric
            r=validate_query_plan(self.cap,self.plan)
            self.assertEqual(r['status'],'validated_structure_not_execution')
            self.assertEqual(r['filters'],self.plan['filters'])
            self.assertEqual(r['time']['date'],'2025-12-31')

    def test_scoped_ratio_denominator_is_visible(self):
        r=validate_query_plan(self.cap,self.plan)
        text=render_plan(self.cap,r)
        self.assertIn('包含空置铺位',text)
        self.assertIn('不是整个项目GLA',text)

    def test_project_only_ratio_keeps_gla(self):
        self.plan['filters']=[];self.plan['group_by']=['project']
        r=validate_query_plan(self.cap,self.plan)
        self.assertFalse(any('不是整个项目GLA' in b for b in r['dimension_basis']))

    def test_invalid_floor_and_unreviewed_join(self):
        self.plan['filters'][1]['values']=['99']
        with self.assertRaises(ValueError):validate_query_plan(self.cap,self.plan)
        self.plan['filters'][1]['values']=['2']
        self.plan['target']['id']='operating_expense'
        self.assertEqual(validate_query_plan(self.cap,self.plan)['status'],'not_implemented')

    def test_unit_list_floor_preserved(self):
        self.plan['target']={'kind':'list','id':'unit'}
        self.plan['time']={'kind':'not_applicable'}
        self.assertEqual(validate_query_plan(self.cap,self.plan)['status'],'validated_structure_not_execution')
