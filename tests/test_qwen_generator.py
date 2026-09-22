from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import (  # noqa: E402
    CorrectionFeedback,
    GenerationRequest,
    QueryRouter,
    QwenSqlGenerator,
)
from dataquery_agent.model_client import ModelResponse, ModelUsage  # noqa: E402


class FakeClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def chat(self, system: str, user: str, max_tokens: int = 1200) -> ModelResponse:
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        return ModelResponse(
            content=self.content,
            model="fake-qwen",
            latency_ms=12,
            usage=ModelUsage(0, 0, 0),
        )


class QwenGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.route = QueryRouter.from_project_root(ROOT).route("2026年8月实收租金是多少？")

    def test_adapter_builds_candidate_without_network(self) -> None:
        client = FakeClient('{"sql":"SELECT 1","summary":"测试"}')
        generator = QwenSqlGenerator(client, ROOT)
        candidate = generator.generate(GenerationRequest("问题", self.route, 1))
        self.assertEqual("SELECT 1", candidate.sql)
        self.assertEqual("fake-qwen", candidate.model)
        payload = json.loads(client.calls[0]["user"])
        self.assertIn("schema", payload)
        self.assertIn("field_conventions", payload)
        self.assertNotIn("correction", payload)

    def test_correction_feedback_is_structured(self) -> None:
        client = FakeClient('```json\n{"sql":"SELECT 1","summary":"已修正"}\n```')
        generator = QwenSqlGenerator(client, ROOT)
        generator.generate(
            GenerationRequest(
                "问题",
                self.route,
                2,
                CorrectionFeedback("unknown_column", "使用真实字段", "SELECT bad FROM x"),
            )
        )
        correction = json.loads(client.calls[0]["user"])["correction"]
        self.assertEqual("unknown_column", correction["error_type"])
        self.assertIn("不改变问题", correction["constraint"])


if __name__ == "__main__":
    unittest.main()
