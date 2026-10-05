import unittest
from copy import deepcopy
from capabilities import load_capabilities
from query_plan import validate_query_plan
from plan_view import render_plan


class TenantRankingTests(unittest.TestCase):
    def setUp(self):
        self.cap=load_capabilities()
        self.plan={'target':{'kind':'metric','id':'overdue_balance'},'filters':[],
                   'time':{'kind':'point','date':'2026-09-01'},
                   'group_by':['project','tenant'],
                   'order_by':{'by':'target_value','direction':'desc','limit':2,'partition_by':['project']}}

    def test_project_tenant_top_n_preserves_identity_and_partition(self):
        r=validate_query_plan(self.cap,self.plan)
        self.assertEqual(r['status'],'validated_structure_not_execution')
        self.assertEqual(r['order_by'],self.plan['order_by'])
        text=render_plan(self.cap,r)
        self.assertIn('tenant_id',text)
        self.assertIn('ÿ����Ŀ�ڷֱ�����',text)
        self.assertIn('ÿ��������Χ��������չʾǰ2��',text)

    def test_global_tenant_top_n_not_partitioned(self):
        self.plan['group_by']=['tenant'];del self.plan['order_by']['partition_by']
        r=validate_query_plan(self.cap,self.plan)
        self.assertEqual(r['status'],'validated_structure_not_execution')
        self.assertNotIn('partition_by',r['order_by'])
        self.assertIn('����ѡ��Ŀ�ϲ�',render_plan(self.cap,r))

    def test_invalid_partitions_and_missing_limit(self):
        for value in ([],['project','tenant'],['month'],['project','project']):
            p=deepcopy(self.plan);p['order_by']['partition_by']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate_query_plan(self.cap,p)
        del self.plan['order_by']['limit']
        with self.assertRaises(ValueError):validate_query_plan(self.cap,self.plan)

    def test_partition_does_not_bypass_metric_dimension_validation(self):
        self.plan['target']['id']='operating_expense'
        self.plan['time']={'kind':'relative','period':'previous_month'}
        self.assertEqual(validate_query_plan(self.cap,self.plan)['status'],'not_implemented')

    def test_no_fabricated_tenant_filter_domain(self):
        self.plan['filters']=[{'dimension':'tenant','operator':'in','values':['�鹹���']}]
        r=validate_query_plan(self.cap,self.plan)
        self.assertEqual(r['status'],'not_implemented')
        self.assertEqual(r['input_plan']['filters'],self.plan['filters'])
