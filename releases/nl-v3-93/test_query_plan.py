import unittest
from capabilities import load_capabilities
from query_plan import validate_query_plan
from plan_view import render_plan


class QueryPlanTests(unittest.TestCase):
    def setUp(self):
        self.cap=load_capabilities()
        self.plan={'target':{'kind':'metric','id':'operating_expense'}, 'filters':[],
                   'time':{'kind':'relative','period':'previous_month'},
                   'group_by':['project_city'], 'order_by':{'by':'target_value','direction':'desc'}}

    def test_city_ranking_is_structure_not_lexical_match(self):
        r=validate_query_plan(self.cap,self.plan)
        self.assertEqual(r['status'],'validated_structure_not_execution')
        self.assertEqual(r['time']['start'],'2026-08-01')
        self.assertFalse(r['coverage_verified'])

    def test_top_n_single_metric_retained_in_structure_and_view(self):
        for direction in ('asc','desc'):
            self.plan['order_by']={'by':'target_value','direction':direction,'limit':3}
            result=validate_query_plan(self.cap,self.plan)
            self.assertEqual(result['order_by']['limit'],3)
            text=render_plan(self.cap,result)
            self.assertIn('前3组',text)
            self.assertIn('从低到高' if direction=='asc' else '从高到低',text)

    def test_invalid_top_n_not_silently_dropped(self):
        for value in (True,0,-1,'3',3.5,1001):
            self.plan['order_by']={'by':'target_value','direction':'desc','limit':value}
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_query_plan(self.cap,self.plan)

    def test_partitioned_ranking_not_silently_converted_to_global(self):
        self.plan['group_by']=['month','project']
        self.plan['order_by']={'by':'target_value','direction':'desc','limit':3,'partition_by':['month']}
        result=validate_query_plan(self.cap,self.plan)
        self.assertEqual(result['status'],'validated_structure_not_execution')
        self.assertEqual(result['order_by']['partition_by'],['month'])
        self.assertIn('不是整体排名',render_plan(self.cap,result))

    def test_expense_category_supported(self):
        self.plan['group_by']=['expense_category']
        self.assertEqual(validate_query_plan(self.cap,self.plan)['status'],'validated_structure_not_execution')

    def test_monthly_trend_is_one_metric_not_multiple_requests(self):
        self.plan['group_by']=['month','project']
        self.plan['order_by']=None
        self.plan['time']={'kind':'range','start':'2026-01-01','end':'2026-06-30'}
        for metric in ('rent_collected','operating_expense','collection_rate','budget_variance'):
            self.plan['target']['id']=metric
            result=validate_query_plan(self.cap,self.plan)
            self.assertEqual(result['status'],'validated_structure_not_execution')
            self.assertEqual(result['group_by'],['month','project'])
            self.assertIn('月份、项目',render_plan(self.cap,result))

    def test_month_does_not_become_filter_or_point_snapshot_series(self):
        self.plan['target']['id']='occupancy_rate'
        self.plan['group_by']=['month']
        self.plan['order_by']=None
        self.assertEqual(validate_query_plan(self.cap,self.plan)['status'],'not_implemented')
        self.plan['filters']=[{'dimension':'month','operator':'in','values':['2026-01']}]
        with self.assertRaises(ValueError):
            validate_query_plan(self.cap,self.plan)

    def test_join_not_invented(self):
        self.plan['target']['id']='rent_due'
        self.plan['group_by']=['expense_category']
        self.assertEqual(validate_query_plan(self.cap,self.plan)['status'],'not_implemented')

    def test_rent_tenant_grouping_uses_current_profile_basis(self):
        self.plan['target']['id']='rent_due'
        self.plan['group_by']=['tenant_tier','tenant_industry']
        result=validate_query_plan(self.cap,self.plan)
        self.assertEqual(result['status'],'validated_structure_not_execution')
        self.assertEqual(result['group_by'],['tenant_tier','tenant_industry'])
        self.assertEqual(len(result['dimension_basis']),2)
        self.assertIn('历史等级变更',render_plan(self.cap,result))

    def test_expenses_not_allocated_to_tenants_without_basis(self):
        self.plan['group_by']=['tenant_tier']
        self.assertEqual(validate_query_plan(self.cap,self.plan)['status'],'not_implemented')

    def test_registered_unimplemented_filter_preserved_as_gap(self):
        self.plan['target']['id']='rent_due'
        self.plan['filters']=[{'dimension':'tenant_industry','operator':'in','values':['餐饮']}]
        r=validate_query_plan(self.cap,self.plan)
        self.assertEqual(r['status'],'not_implemented')
        self.assertEqual(r['filters'],self.plan['filters'])
        self.assertFalse(r['filter_values_verified'])
        self.assertIn('餐饮',r['message'])

    def test_pending_domain_does_not_allow_invented_project(self):
        self.plan['filters']=[{'dimension':'tenant_tier','operator':'in','values':['anchor']},
                              {'dimension':'project','operator':'in','values':['虚构项目']}]
        with self.assertRaises(ValueError): validate_query_plan(self.cap,self.plan)

    def test_unregistered_filter_still_fails_contract(self):
        self.plan['filters']=[{'dimension':'mystery_dimension','operator':'in','values':['x']}]
        with self.assertRaises(ValueError): validate_query_plan(self.cap,self.plan)

    def test_unknown_and_duplicate_groups(self):
        for groups in [['imaginary'],['project','project']]:
            self.plan['group_by']=groups
            with self.subTest(groups=groups),self.assertRaises(ValueError):
                validate_query_plan(self.cap,self.plan)

    def test_ranking_without_group_not_silently_dropped(self):
        self.plan['group_by']=[]
        with self.assertRaises(ValueError):
            validate_query_plan(self.cap,self.plan)

    def test_missing_time_propagates_clarification(self):
        self.plan['time']={'kind':'missing'}
        self.assertEqual(validate_query_plan(self.cap,self.plan)['status'],'clarify')

    def test_missing_time_retains_known_single_query_slots(self):
        self.plan['time']={'kind':'missing'}
        self.plan['filters']=[{'dimension':'project','operator':'in','values':['澄明广场']}]
        r=validate_query_plan(self.cap,self.plan)
        self.assertEqual(r['status'],'clarify')
        self.assertEqual(r['target'],self.plan['target'])
        self.assertEqual(r['filters'],self.plan['filters'])
        self.assertEqual(r['group_by'],self.plan['group_by'])
        self.assertEqual(r['order_by'],self.plan['order_by'])
        self.plan['filters'][0]['values'].append('changed')
        self.assertEqual(r['input_plan']['filters'][0]['values'],['澄明广场'])
        self.assertFalse(r['retained_input_verified'])

    def test_unknown_fields_not_ignored(self):
        self.plan['hidden_second_question']='extra'
        with self.assertRaises(ValueError):
            validate_query_plan(self.cap,self.plan)

    def test_disclosure_metadata_retained(self):
        self.plan['target']['id']='collection_rate'
        self.assertTrue(validate_query_plan(self.cap,self.plan)['disclosure_required'])


if __name__=='__main__':
    unittest.main()
