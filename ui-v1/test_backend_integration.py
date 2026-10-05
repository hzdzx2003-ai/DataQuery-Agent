"""Real fixed SQL against a freshly generated fictional fixture only."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from adapter import default_release, SavedCases
from query_service import frozen_modules, understand, execute_confirmed


class BackendIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen_modules()
        cls.temp = tempfile.TemporaryDirectory(prefix='dataquery-synthetic-')
        root = default_release()
        spec = importlib.util.spec_from_file_location('ui_fixture_generator', root / 'scripts/generate_synthetic_data.py')
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        # Redirect generated outputs only; the frozen generator source stays unchanged.
        generator.OUTPUT_DIR = Path(cls.temp.name)
        generator.DB_PATH = generator.OUTPUT_DIR / 'fixture.sqlite3'
        with contextlib.redirect_stdout(io.StringIO()):
            generator.main()
        from fixed_backend.compiler import open_readonly
        cls.connection = open_readonly(generator.DB_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()
        cls.temp.cleanup()

    def test_all_saved_decisions_match_original_outputs(self):
        from fixed_backend.compiler import execute_decision
        from verify_release import same
        store = SavedCases()
        for row in store.catalog():
            record = store.open(row['id'])
            actual = execute_confirmed(record['decision'], lambda d: execute_decision(self.connection, d))
            self.assertTrue(same(actual, record['result']), row['id'])

    def test_injected_parser_to_real_fixed_backend(self):
        from fixed_backend.compiler import execute_decision
        question = '列出租户'
        response = {'requests':[{'source_text':question, 'kind':'query','plans':[
            {'target':{'kind':'list','id':'tenant'},'filters':[],
             'time':{'kind':'not_applicable'},'group_by':[],'order_by':None}]}]}
        decision = understand(question, lambda *args: json.dumps(response))
        result = execute_confirmed(decision, lambda d: execute_decision(self.connection, d))
        self.assertEqual(result['status'], 'executed')
        self.assertGreater(len(result['rows']), 0)

    def test_database_connection_is_read_only(self):
        import sqlite3
        with self.assertRaises(sqlite3.DatabaseError):
            self.connection.execute('DELETE FROM tenants')
