from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(Path(__file__).with_name('app.py')), default_timeout=20).run()

    def test_initial_and_repeat_submission(self):
        app = self.app()
        self.assertFalse(app.exception)
        app.button(key='open_case').click().run()
        self.assertFalse(app.exception)
        first = app.session_state['record']['id']
        app.button(key='open_case').click().run()
        self.assertEqual(app.session_state['record']['id'], first)
        self.assertFalse(app.exception)

    def test_own_question_is_separate_from_saved_answer(self):
        app = self.app()
        app.text_area(key='own_question').input('全新问题，不应替换成旧答案').run()
        with self.assertRaises(KeyError):
            app.session_state['record']
        self.assertTrue(app.button(key='live_submit').disabled)
        self.assertFalse(app.exception)

    def test_non_query_categories(self):
        for category in ['口径确认', '数据范围说明']:
            app = self.app()
            app.selectbox[0].select(category).run()
            app.button(key='open_case').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['record']['result']['status'], 'not_executed')

    def test_live_disabled(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key='live_submit').disabled)
        self.assertFalse(app.text_area[0].disabled)

    def test_case_change_clears_old_result(self):
        app = self.app()
        app.button(key='open_case').click().run()
        app.selectbox[1].select('STA002').run()
        with self.assertRaises(KeyError):
            app.session_state['record']
        self.assertFalse(app.exception)

    def test_clarification_draft_and_case_change(self):
        app = self.app()
        app.selectbox[0].select('口径确认').run()
        app.button(key='open_case').click().run()
        app.text_input[0].input('请按实收口径')
        app.button(key='save_clarification').click().run()
        self.assertFalse(app.session_state['clarification_draft']['execution_allowed'])
        self.assertEqual(app.session_state['record']['result']['status'], 'not_executed')
        app.selectbox[0].select('数据查询').run()
        with self.assertRaises(KeyError):
            app.session_state['clarification_draft']
        self.assertFalse(app.exception)

    def test_every_saved_case_renders(self):
        from adapter import SavedCases
        app = self.app()
        for case in SavedCases().catalog():
            app.selectbox[1].select(case['id']).run()
            app.button(key='open_case').click().run()
            self.assertFalse(app.exception, case['id'])
            self.assertEqual(app.session_state['record']['id'], case['id'])

    def test_recommendations_open_correct_types(self):
        app = self.app()
        for action in ['query_candidate', 'clarify', 'reject']:
            app.button(key='recommend_'+action).click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['record']['decision']['action'], action)

    def test_metric_units(self):
        from presentation import metric_display
        def decision(ident):
            return {'requests': [{'plans': [{'target': {'id': ident}}]}]}
        self.assertEqual(metric_display(decision('occupancy_rate'), .93)[1], '93.00%')
        self.assertEqual(metric_display(decision('rent_due'), 1200)[1], '1,200.00 元')
        self.assertEqual(metric_display(decision('leased_area'), None)[1], '暂无数据')

    def test_table_format_does_not_change_source(self):
        from presentation import display_rows
        source = [{'project':'测试项目', 'value':.75}]
        decision = {'requests':[{'plans':[{'target':{'id':'collection_rate'}}]}]}
        self.assertEqual(display_rows(decision, source), [{'项目':'测试项目', '租金收缴率':'75.00%'}])
        self.assertEqual(source[0]['value'], .75)

    def test_summary_keeps_disclosures(self):
        from adapter import SavedCases
        from presentation import summary_lines
        store = SavedCases()
        for case in store.catalog():
            decision = store.open(case['id'])['decision']
            original = decision.get('summary_message') or decision.get('message') or '暂无摘要'
            self.assertEqual(summary_lines(decision), [s.strip() for s in original.splitlines() if s.strip()])


if __name__ == '__main__':
    unittest.main()
