from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent.model_client import ModelClientError, parse_json_object  # noqa: E402


class ModelClientTests(unittest.TestCase):
    def test_plain_and_fenced_json_are_parsed(self) -> None:
        self.assertEqual({"sql": "SELECT 1"}, parse_json_object('{"sql":"SELECT 1"}'))
        self.assertEqual(
            {"sql": "SELECT 1"},
            parse_json_object('```json\n{"sql":"SELECT 1"}\n```'),
        )

    def test_non_json_output_is_rejected(self) -> None:
        with self.assertRaises(ModelClientError):
            parse_json_object("SELECT 1")


if __name__ == "__main__":
    unittest.main()
