from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import QueryRouter, require_executable  # noqa: E402


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router = QueryRouter.from_project_root(ROOT)

    def test_development_set_actions(self) -> None:
        cases = json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
        development_cases = [case for case in cases if case["split"] == "development"]
        self.assertEqual(16, len(development_cases))
        for case in development_cases:
            with self.subTest(case_id=case["id"]):
                decision = self.router.route(case["question"])
                self.assertEqual(case["expected_action"], decision.action)

    def test_write_request_has_highest_priority(self) -> None:
        decision = self.router.route("删除上海项目的实收租金记录")
        self.assertEqual("reject", decision.action)
        self.assertEqual("dangerous_write", decision.reason_code)

    def test_write_variants_are_rejected_but_read_only_history_is_not(self) -> None:
        dangerous = [
            "把2025年的欠租记录抹掉",
            "清除2025年的欠租记录",
            "刪除上海項目的租約",
            "ＤＥＬＥＴＥ FROM leases",
            "删\u200b除2025年的欠租记录",
            "truncate table leases",
            "alter table leases add column x",
            "移除上海项目的租约",
            "把上海项目的月租金改成0",
            "新增一份上海项目的租约记录",
        ]
        for question in dangerous:
            with self.subTest(question=question):
                self.assertEqual("reject", self.router.route(question).action)
        for question in ("最近更新的租约有哪些？", "被修改过的租约有哪些？"):
            with self.subTest(question=question):
                decision = self.router.route(question)
                self.assertNotEqual("dangerous_write", decision.reason_code)
                self.assertNotEqual("reject", decision.action)

    def test_query_wording_changes_are_not_data_writes(self) -> None:
        harmless = [
            "帮我修改成按季度汇总",
            "把统计口径改成按面积",
            "更新一下查询条件，按月份来",
            "换成按实收租金统计",
        ]
        for question in harmless:
            with self.subTest(question=question):
                self.assertNotEqual("dangerous_write", self.router.route(question).reason_code)
        dangerous = [
            "把上海项目的月租金改成0",
            "把上海项目的月租金调整为5万",
            "修改租约状态为过期",
        ]
        for question in dangerous:
            with self.subTest(question=question):
                decision = self.router.route(question)
                self.assertEqual("reject", decision.action)
                self.assertEqual("dangerous_write", decision.reason_code)

    def test_explicit_income_metric_does_not_clarify(self) -> None:
        decision = self.router.route("2026年8月上海实收租金收入是多少？")
        self.assertEqual("execute", decision.action)
        self.assertIn("rent_collected", decision.metric_ids)

    def test_collection_rate_discloses_default(self) -> None:
        decision = self.router.route("2026年8月各项目租金回款率是多少？")
        self.assertEqual("execute_with_disclosure", decision.action)
        self.assertEqual(("collection_rate",), decision.metric_ids)
        self.assertIn("按账期", decision.disclosures[0])

    def test_explicit_occupancy_basis_executes_without_disclosure(self) -> None:
        decision = self.router.route("截至2026年9月1日按面积计算出租率")
        self.assertEqual("execute", decision.action)

    def test_bare_noi_requires_clarification(self) -> None:
        decision = self.router.route("2026年8月各项目NOI是多少？")
        self.assertEqual("clarify", decision.action)
        self.assertEqual("noi_scope", decision.reason_code)

    def test_cash_noi_uses_boundary_disclosure(self) -> None:
        decision = self.router.route("2026年8月现金净运营收益是多少？")
        self.assertEqual("execute_with_disclosure", decision.action)
        self.assertIn("不等于正式 NOI", decision.disclosures[0])

    def test_explicit_recent_window_is_not_blocked(self) -> None:
        questions = [
            "最近90天到期的租约有哪些？",
            "最近三个月到期的租约有哪些？",
            "最近一个月的实收租金是多少？",
            "最近半年的实收租金",
            "离我最近的项目有哪些？",
        ]
        for question in questions:
            with self.subTest(question=question):
                self.assertNotEqual("clarify", self.router.route(question).action)

    def test_unknown_metrics_never_execute(self) -> None:
        questions = [
            "各项目上个月的销售额是多少",
            "各项目的客流量是多少",
            "各城市的租户满意度",
            "哪个项目租户满意度最低",
            "各项目的坪效",
            "各项目的会员复购率",
            "各项目的员工满意度",
            "各项目的出租率和客流量",
        ]
        for question in questions:
            with self.subTest(question=question):
                self.assertNotIn(self.router.route(question).action, {"execute", "execute_with_disclosure"})

    def test_entity_lists_still_execute(self) -> None:
        for question in ("列出所有项目", "哪些租约在11月到期？", "租户名单有哪些？"):
            with self.subTest(question=question):
                self.assertEqual("execute", self.router.route(question).action)

    def test_alternative_metric_basis_is_rejected(self) -> None:
        questions = [
            "按到账日统计2026年8月各项目的收缴率",
            "截至2026年9月1日按铺位数计算各城市出租率",
            "2026年8月各项目实收租金，含税",
        ]
        for question in questions:
            with self.subTest(question=question):
                self.assertEqual("reject", self.router.route(question).action)

    def test_semantic_ambiguity_variants_clarify(self) -> None:
        questions = [
            "哪个项目业绩最好",
            "最差的项目是哪个",
            "哪些租户欠款最严重",
            "哪些是重点租户",
            "杭州的租户有哪些",
        ]
        for question in questions:
            with self.subTest(question=question):
                self.assertEqual("clarify", self.router.route(question).action)

    def test_non_executable_decisions_cannot_reach_sql_generation(self) -> None:
        for question in ("删除租约", "上海上个月的收入是多少？"):
            with self.subTest(question=question), self.assertRaises(ValueError):
                require_executable(self.router.route(question))
        self.assertEqual(
            "execute",
            require_executable(self.router.route("2026年8月实收租金是多少？")).action,
        )

    def test_policy_and_catalog_are_consistent(self) -> None:
        disclosures = self.router.policy["disclosures"]
        for metric in self.router.metrics.values():
            if metric.get("disclosure_required"):
                self.assertIn(metric["id"], disclosures)
        valid_special = {
            "unsupported_formal_profit",
            "unsupported_formal_noi",
            "time_window",
            "time_window_custom",
            "severity_rule",
            "monthly_rent",
            "tenant_tier",
            "property_city",
            "tenant_registered_city",
        }
        for rule in self.router.policy["clarification_rules"].values():
            for option in rule.get("options", []):
                self.assertIn(option["id"], set(self.router.metrics) | valid_special)

    def test_metric_order_is_stable_across_hash_seeds(self) -> None:
        code = (
            "import json,sys;from pathlib import Path;sys.path.insert(0,'src');"
            "from dataquery_agent import QueryRouter;"
            "print(json.dumps(QueryRouter.from_project_root(Path('.')).route("
            "'各项目的应收和实收').to_dict(),ensure_ascii=False,sort_keys=True))"
        )
        outputs = []
        for seed in ("1", "98765"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONUTF8="1")
            outputs.append(
                subprocess.check_output(
                    [sys.executable, "-c", code],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    encoding="utf-8",
                )
            )
        self.assertEqual(outputs[0], outputs[1])

    def test_decision_is_json_serializable(self) -> None:
        decision = self.router.route("哪个项目表现最好？")
        json.dumps(decision.to_dict(), ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
