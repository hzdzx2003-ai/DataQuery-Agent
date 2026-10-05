import json
import unittest
from copy import deepcopy
from capabilities import load_capabilities
from json_resolver import JsonResolver,normalize_empty_grouping


class FormatNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.value={'requests':[{'source_text':'测试','kind':'query','plans':[{
            'target':{'kind':'metric','id':'rent_collected'},'filters':[],
            'time':{'kind':'relative','period':'previous_month'},'group_by':None,'order_by':None}]}]}

    def test_null_grouping_without_mutating_raw(self):
        original=deepcopy(self.value);v,changes=normalize_empty_grouping(self.value)
        self.assertEqual(v['requests'][0]['plans'][0]['group_by'],[])
        self.assertEqual(self.value,original);self.assertEqual(len(changes),1)
        self.assertIsNone(v['requests'][0]['plans'][0]['order_by'])

    def test_no_retry_and_normalization_trace(self):
        calls=[]
        def client(*_):calls.append(1);return json.dumps(self.value)
        resolver=JsonResolver(load_capabilities(),client)
        resolver('prompt','测试')
        self.assertEqual(len(calls),1)
        self.assertEqual(len(resolver.trace[0]['format_normalizations']),1)

    def test_missing_grouping_or_bad_filter_not_invented(self):
        p=self.value['requests'][0]['plans'][0];del p['group_by'];p['filters']=None
        v,changes=normalize_empty_grouping(self.value)
        self.assertEqual(changes,[])
        self.assertNotIn('group_by',v['requests'][0]['plans'][0])
        self.assertIsNone(v['requests'][0]['plans'][0]['filters'])
