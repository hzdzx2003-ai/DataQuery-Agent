import unittest
from unittest.mock import patch
from adapter import SavedCases, ReleaseError, clarification_draft
from pathlib import Path


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = SavedCases()

    def test_complete_catalog(self):
        self.assertEqual(len(self.store.catalog()), 100)

    def test_all_saved_records(self):
        for row in self.store.catalog():
            result = self.store.open(row['id'])
            self.assertFalse(result['model_called'])
            self.assertFalse(result['database_queried'])
            if row['action'] != 'query_candidate':
                self.assertEqual(result['result']['status'], 'not_executed')

    def test_no_fuzzy_substitution(self):
        self.assertIsNone(self.store.find_exact('任意新问题'))
        row = self.store.catalog()[0]
        self.assertEqual(self.store.find_exact(row['question'])['id'], row['id'])

    def test_defensive_copy(self):
        result = self.store.open('STA001')
        result['decision']['action'] = 'reject'
        self.assertEqual(self.store.open('STA001')['decision']['action'], 'query_candidate')

    def test_clarification_does_not_execute(self):
        draft = clarification_draft('原问题', '按实收')
        self.assertTrue(draft['requires_reparse'])
        self.assertFalse(draft['execution_allowed'])
        with self.assertRaises(ValueError):
            clarification_draft('原问题', '  ')

    def test_corrupt_artifact_rejected(self):
        original = Path.read_bytes
        def corrupted(path):
            return b'{}' if path.name == 'decisions.json' else original(path)
        with patch.object(Path, 'read_bytes', corrupted):
            with self.assertRaises(ReleaseError):
                SavedCases()

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ReleaseError):
            SavedCases._index([{'id':'same'}, {'id':'same'}])


if __name__ == '__main__':
    unittest.main()
