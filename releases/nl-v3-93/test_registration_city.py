import unittest
from capabilities import load_capabilities
from query_plan import validate_query_plan
from plan_view import render_plan


class RegistrationCityTests(unittest.TestCase):
    def setUp(self):
        self.cap = load_capabilities()
        self.plan = {'target': {'kind': 'metric', 'id': 'rent_due'},
                     'filters': [{'dimension': 'tenant_registration_city',
                                  'operator': 'in', 'values': ['北京']}],
                     'time': {'kind': 'relative', 'period': 'previous_month'},
                     'group_by': [], 'order_by': None}

    def test_registration_filter_does_not_invent_project_filter(self):
        result = validate_query_plan(self.cap, self.plan)
        self.assertEqual(result['status'], 'validated_structure_not_execution')
        self.assertEqual(result['filters'], self.plan['filters'])
        self.assertIn('租户注册城市', render_plan(self.cap, result))
        self.assertIn('不自动缩小项目范围', result['dimension_basis'][0])

    def test_distinct_city_filters_coexist(self):
        self.plan['filters'].append({'dimension': 'project_city', 'operator': 'in', 'values': ['上海']})
        result = validate_query_plan(self.cap, self.plan)
        self.assertEqual(result['status'], 'validated_structure_not_execution')
        self.assertEqual(len(result['filters']), 2)

    def test_registration_grouping_and_list(self):
        self.plan['group_by'] = ['tenant_registration_city']
        self.assertEqual(validate_query_plan(self.cap, self.plan)['status'], 'validated_structure_not_execution')
        self.plan['target'] = {'kind': 'list', 'id': 'tenant'}
        self.plan['time'] = {'kind': 'not_applicable'}
        self.assertEqual(validate_query_plan(self.cap, self.plan)['status'], 'validated_structure_not_execution')

    def test_unknown_city_refused(self):
        self.plan['filters'][0]['values'] = ['不存在的城市']
        with self.assertRaises(ValueError):
            validate_query_plan(self.cap, self.plan)

    def test_no_unverified_expense_join(self):
        self.plan['target']['id'] = 'operating_expense'
        self.assertEqual(validate_query_plan(self.cap, self.plan)['status'], 'not_implemented')
