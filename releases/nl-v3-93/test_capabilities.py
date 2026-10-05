import json
import tempfile
import unittest
from pathlib import Path
from capabilities import load_capabilities, build_understanding_prompt, validate_target_and_filters


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.cap = load_capabilities()

    def test_business_information_reaches_prompt(self):
        prompt = build_understanding_prompt(self.cap)
        for p in self.cap['context']['projects']:
            self.assertIn(p['name'], prompt)
        for s in ['2026-09-01', 'project_city', 'tenant_tier', 'expense_category', 'rent_due']:
            self.assertIn(s, prompt)
        self.assertEqual(len(self.cap['metrics']), 10)

    def test_no_regex_or_sql_formula_in_projected_metrics(self):
        for metric in self.cap['metrics']:
            self.assertNotIn('patterns', metric)
            self.assertNotIn('formula', metric)
            self.assertIn('default_assumption', metric)

    def test_legacy_keyword_clarification_rules_not_sent(self):
        from copy import deepcopy
        before=deepcopy(self.cap)
        prompt=build_understanding_prompt(self.cap)
        self.assertNotIn('"ambiguous_expressions"',prompt)
        self.assertNotIn('��Ҫ�û�������ȷʱ�䴰��',prompt)
        self.assertEqual(self.cap,before)
        self.assertIn('���',self.cap['ambiguous_expressions'])

    def test_definitions_defaults_and_coverage_survive_projection(self):
        prompt=build_understanding_prompt(self.cap)
        for metric in self.cap['metrics']:
            for key in ('id','definition','default_assumption'):
                self.assertIn(json.dumps(metric[key],ensure_ascii=False),prompt)
        self.assertIn('"data_period"',prompt)
        self.assertIn('"reference_date"',prompt)

    def test_policy_does_not_turn_true_unknowns_into_defaults(self):
        from clarification_policy import CLARIFICATION_POLICY
        from conversation import ENVELOPE_INSTRUCTIONS
        self.assertTrue(ENVELOPE_INSTRUCTIONS.endswith(CLARIFICATION_POLICY))
        self.assertEqual((build_understanding_prompt(self.cap)+ENVELOPE_INSTRUCTIONS).count(CLARIFICATION_POLICY),1)
        self.assertIn('Ĭ�ϲ������û�����δ֪��λ',CLARIFICATION_POLICY)
        self.assertIn('�Դ��ڻ�ı�𰸵�δ��ѡ��',CLARIFICATION_POLICY)
        self.assertIn('��Ҫ���ظ�������Ŀ',CLARIFICATION_POLICY)

    def test_target_is_separate_from_filter(self):
        out = validate_target_and_filters(self.cap, {'kind':'metric','id':'rent_due'},
            [{'dimension':'project','operator':'in','values':['�����㳡']}])
        self.assertEqual(out['target'], {'kind':'metric','id':'rent_due'})
        self.assertNotIn('entity_ids', out)

    def test_list_is_a_distinct_target(self):
        out = validate_target_and_filters(self.cap, {'kind':'list','id':'lease'}, [])
        self.assertEqual(out['target']['id'], 'lease')

    def test_unknown_metric_and_project_fail(self):
        with self.assertRaises(ValueError):
            validate_target_and_filters(self.cap, {'kind':'metric','id':'footfall'}, [])
        with self.assertRaises(ValueError):
            validate_target_and_filters(self.cap, {'kind':'metric','id':'rent_due'},
                [{'dimension':'project','operator':'in','values':['�鹹��Ŀ']}])

    def test_unknown_filter_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            validate_target_and_filters(self.cap, {'kind':'list','id':'lease'},
                [{'dimension':'unknown','operator':'in','values':['foo']}])

    def test_reference_date_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'context.json'
            context = dict(self.cap['context'], reference_date='2026-10-01')
            p.write_text(json.dumps(context), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'reference dates'):
                load_capabilities(context_path=p)

    def test_incomplete_explanations_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'context.json'
            context = dict(self.cap['context'], metric_explanations={})
            p.write_text(json.dumps(context), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'explanations'):
                load_capabilities(context_path=p)

    def test_bad_list_grouping_config_refused_before_prompt(self):
        for groups in ({}, {'property':['imaginary'],'unit':[],'tenant':[],'lease':[]}):
            with self.subTest(groups=groups),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'context.json'
                context=dict(self.cap['context'],list_grouping_dimensions=groups)
                p.write_text(json.dumps(context),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'list dimension'):
                    load_capabilities(context_path=p)

    def test_implementation_limits_disclosed_without_dropping_conditions(self):
        prompt = build_understanding_prompt(self.cap)
        self.assertIn('���������������ʵ��', prompt)
        self.assertIn('�������������ڼƻ���', prompt)


if __name__ == '__main__':
    unittest.main()
