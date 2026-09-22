from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent.ui_support import attempts_for_display, format_display_rows, load_demo_records  # noqa: E402


class UiSupportTests(unittest.TestCase):
    def test_missing_demo_artifact_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual([], load_demo_records(Path(temporary)))

    def test_demo_artifact_and_trace_are_joined(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trace_dir = root / "evaluation" / "results" / "phase3-traces"
            trace_dir.mkdir(parents=True)
            trace = {
                "columns": ["name"],
                "rows": [["示例"]],
                "attempts": [{"attempt_number": 1, "status": "succeeded", "sql": "SELECT 1"}],
            }
            (trace_dir / "D2-001.json").write_text(json.dumps(trace), encoding="utf-8")
            artifact = {
                "results": [{
                    "case_id": "D2-001",
                    "question": "示例问题",
                    "status": "succeeded",
                    "strict_row_match": True,
                    "trace_file": "evaluation/results/phase3-traces/D2-001.json",
                }]
            }
            (trace_dir.parent / "phase3-development-live.json").write_text(
                json.dumps(artifact), encoding="utf-8"
            )
            records = load_demo_records(root)
        self.assertEqual(1, len(records))
        self.assertEqual("SELECT 1", records[0].final_sql)
        self.assertEqual([["示例"]], records[0].rows)

    def test_trace_display_uses_product_labels(self) -> None:
        rows = attempts_for_display(
            {"attempts": [{"attempt_number": 1, "status": "failed", "failure_stage": "precheck"}]}
        )
        self.assertEqual("未完成", rows[0]["状态"])
        self.assertEqual("生成前校验", rows[0]["阶段"])

    def test_numbers_are_formatted_for_display_only(self) -> None:
        self.assertEqual(
            [["510,748.28", "0.7533", 3]],
            format_display_rows([[510748.27999999997, 0.7533, 3]]),
        )

    def test_constructed_scenarios_are_clearly_labeled(self) -> None:
        records = load_demo_records(ROOT)
        scenarios = [record for record in records if record.case_id.startswith("UI-")]
        self.assertEqual(5, len(scenarios))
        self.assertTrue(all("非真实模型结果" in record.evidence_label for record in scenarios))
        self.assertEqual(
            {"clarify", "reject", "succeeded", "failed"},
            {record.status for record in scenarios},
        )


if __name__ == "__main__":
    unittest.main()
