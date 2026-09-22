from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import QueryPipeline, QueryRouter, ReadOnlySqlGuard, SqlCandidate  # noqa: E402


class SequenceGenerator:
    def __init__(self, candidates: list[SqlCandidate]) -> None:
        self.candidates = candidates
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.candidates[len(self.requests) - 1]


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router = QueryRouter.from_project_root(ROOT)
        cls.guard = ReadOnlySqlGuard(ROOT / "data" / "generated" / "commercial_real_estate.sqlite3")

    def pipeline(self, candidates: list[SqlCandidate], max_attempts: int = 3):
        generator = SequenceGenerator(candidates)
        return QueryPipeline(self.router, generator, self.guard, max_attempts), generator

    def test_clarify_never_calls_generator(self) -> None:
        pipeline, generator = self.pipeline([])
        run = pipeline.run("上海上个月的租金收入是多少？")
        self.assertEqual("clarify", run.status)
        self.assertEqual((), run.attempts)
        self.assertEqual([], generator.requests)

    def test_first_attempt_success_is_traced(self) -> None:
        pipeline, generator = self.pipeline([SqlCandidate("SELECT COUNT(*) AS count FROM properties")])
        run = pipeline.run("项目名单有哪些？")
        self.assertEqual("succeeded", run.status)
        self.assertEqual(1, len(run.attempts))
        self.assertEqual(6, run.rows[0][0])
        self.assertIsNone(generator.requests[0].feedback)
        self.assertEqual("", run.user_message)

    def test_unknown_column_is_corrected_on_second_attempt(self) -> None:
        pipeline, generator = self.pipeline(
            [
                SqlCandidate("SELECT missing_column FROM properties"),
                SqlCandidate("SELECT property_name FROM properties ORDER BY property_name"),
            ]
        )
        run = pipeline.run("列出所有项目")
        self.assertEqual("succeeded", run.status)
        self.assertEqual(2, len(run.attempts))
        self.assertEqual("unknown_column", run.attempts[0].error_type)
        self.assertEqual("unknown_column", generator.requests[1].feedback.error_type)
        self.assertEqual("execution", run.attempts[0].failure_stage)
        self.assertIsNotNone(run.attempts[0].execution_error)
        self.assertTrue(run.attempts[0].recovered_later)
        self.assertTrue(run.recovered)
        self.assertIn("已自动修正后完成", run.user_message)
        self.assertEqual(6, len(run.rows))

    def test_forbidden_sql_never_executes_and_can_be_corrected(self) -> None:
        before = self.guard.execute("SELECT COUNT(*) FROM leases")[1][0][0]
        pipeline, _ = self.pipeline(
            [
                SqlCandidate("DELETE FROM leases"),
                SqlCandidate("SELECT COUNT(*) FROM leases"),
            ]
        )
        run = pipeline.run("租约名单有哪些？")
        after = self.guard.execute("SELECT COUNT(*) FROM leases")[1][0][0]
        self.assertEqual("succeeded", run.status)
        self.assertEqual("forbidden_operation", run.attempts[0].error_type)
        self.assertEqual("precheck", run.attempts[0].failure_stage)
        self.assertIsNotNone(run.attempts[0].precheck_error)
        self.assertEqual(before, after)

    def test_attempt_limit_is_enforced(self) -> None:
        pipeline, generator = self.pipeline(
            [SqlCandidate("SELECT nope FROM properties") for _ in range(3)],
            max_attempts=3,
        )
        run = pipeline.run("列出所有项目")
        self.assertEqual("failed", run.status)
        self.assertEqual(3, len(run.attempts))
        self.assertEqual(3, len(generator.requests))
        self.assertFalse(run.recovered)
        self.assertTrue(all(not attempt.recovered_later for attempt in run.attempts))
        self.assertIn("自动修正了 3 次", run.user_message)
        self.assertIn("明确指标和时间范围", run.user_message)

    def test_empty_result_is_success_and_does_not_retry(self) -> None:
        pipeline, generator = self.pipeline(
            [
                SqlCandidate("SELECT property_name FROM properties WHERE 1 = 0"),
                SqlCandidate("SELECT property_name FROM properties"),
            ]
        )
        run = pipeline.run("列出所有项目")
        self.assertEqual("succeeded", run.status)
        self.assertEqual(0, run.attempts[0].row_count)
        self.assertEqual(1, len(generator.requests))

    def test_error_normalization_taxonomy(self) -> None:
        from dataquery_agent.pipeline import normalize_sql_error

        examples = {
            "unknown_table": "no such table: x",
            "unknown_column": "no such column: x",
            "ambiguous_column": "ambiguous column name: id",
            "invalid_join": "invalid join condition",
            "syntax": "near FROM: syntax error",
            "type_mismatch": "datatype mismatch",
            "forbidden_operation": "Only SELECT or WITH queries are allowed",
            "empty_result": "no rows returned",
            "timeout": "query timed out",
            "other": "database disk image is malformed",
        }
        for expected, message in examples.items():
            with self.subTest(expected=expected):
                self.assertEqual(expected, normalize_sql_error(message))

    def test_trace_is_json_serializable(self) -> None:
        pipeline, _ = self.pipeline([SqlCandidate("SELECT property_name FROM properties")])
        run = pipeline.run("列出所有项目")
        json.dumps(run.to_dict(), ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
