from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import JsonTraceStore, QueryPipeline, QueryRouter, ReadOnlySqlGuard, SqlCandidate  # noqa: E402


class SequenceGenerator:
    def __init__(self) -> None:
        self.index = 0

    def generate(self, _request):
        candidates = (
            SqlCandidate("SELECT missing_column FROM properties", model="test-model"),
            SqlCandidate("SELECT property_name FROM properties", model="test-model"),
        )
        candidate = candidates[self.index]
        self.index += 1
        return candidate


class TraceStoreTests(unittest.TestCase):
    def test_full_attempt_history_is_persisted_without_transport_secrets(self) -> None:
        router = QueryRouter.from_project_root(ROOT)
        guard = ReadOnlySqlGuard(ROOT / "data" / "generated" / "commercial_real_estate.sqlite3")
        run = QueryPipeline(router, SequenceGenerator(), guard).run("列出所有项目")
        with tempfile.TemporaryDirectory() as temporary:
            path = JsonTraceStore(Path(temporary)).save("run-001", run)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(2, len(payload["attempts"]))
        self.assertTrue(payload["attempts"][0]["recovered_later"])
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        for forbidden in ("api_key", "authorization", "request_headers", "base_url"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
