import json
import unittest
from query_service import understand, execute_confirmed


class ServiceTests(unittest.TestCase):
    def test_fake_client_through_frozen_parser(self):
        question = '列出租户'
        raw = {'requests':[{'source_text':question, 'kind':'query', 'plans':[
            {'target':{'kind':'list','id':'tenant'}, 'filters':[],
             'time':{'kind':'not_applicable'}, 'group_by':[], 'order_by':None}]}]}
        decision = understand(question, lambda *args: json.dumps(raw))
        self.assertEqual(decision['action'], 'query_candidate')
        self.assertEqual(execute_confirmed(decision, lambda d: {'status':'fake_executed'})['status'], 'fake_executed')

    def test_failed_client_never_executes(self):
        def fail(*args):
            raise RuntimeError('private provider text')
        decision = understand('租金', fail)
        self.assertEqual(decision['action'], 'parser_error')
        self.assertNotIn('private provider', str(decision))
        result = execute_confirmed(decision, lambda d: self.fail('must not execute'))
        self.assertEqual(result['status'], 'not_executed')

    def test_clarify_never_executes(self):
        result = execute_confirmed({'action':'clarify'}, lambda d: self.fail('must not execute'))
        self.assertEqual(result['status'], 'not_executed')

    def test_blank_does_not_call_client(self):
        with self.assertRaises(ValueError):
            understand(' ', lambda *args: self.fail('must not call'))
