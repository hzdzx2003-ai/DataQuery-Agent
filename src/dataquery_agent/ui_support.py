from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DemoRecord:
    case_id: str
    question: str
    status: str
    strict_row_match: bool | None
    trace: dict[str, object]
    evidence_label: str = "已验证开发记录"

    @property
    def final_sql(self) -> str:
        attempts = self.trace.get("attempts", [])
        return str(attempts[-1].get("sql", "")) if attempts else ""

    @property
    def columns(self) -> list[str]:
        return [str(item) for item in self.trace.get("columns", [])]

    @property
    def rows(self) -> list[list[object]]:
        return [list(row) for row in self.trace.get("rows", [])]


def load_demo_records(project_root: Path) -> list[DemoRecord]:
    result_path = project_root / "evaluation" / "results" / "phase3-development-live.json"
    records: list[DemoRecord] = []
    if result_path.exists():
        artifact = json.loads(result_path.read_text(encoding="utf-8"))
        for item in artifact.get("results", []):
            trace_path = project_root / str(item["trace_file"])
            if not trace_path.exists():
                continue
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            records.append(
                DemoRecord(
                    case_id=str(item["case_id"]),
                    question=str(item["question"]),
                    status=str(item["status"]),
                    strict_row_match=item.get("strict_row_match"),
                    trace=trace,
                )
            )
    scenario_path = project_root / "data" / "demo_scenarios.json"
    if scenario_path.exists():
        for item in json.loads(scenario_path.read_text(encoding="utf-8")):
            records.append(
                DemoRecord(
                    case_id=str(item["id"]),
                    question=str(item["question"]),
                    status=str(item["trace"]["status"]),
                    strict_row_match=None,
                    trace=item["trace"],
                    evidence_label="构造的界面状态（非真实模型结果）",
                )
            )
    return records


def attempts_for_display(trace: dict[str, object]) -> list[dict[str, object]]:
    stage_labels = {
        "precheck": "生成前校验",
        "execution": "数据库执行",
    }
    error_labels = {
        "unknown_table": "表不存在",
        "unknown_column": "字段不存在",
        "ambiguous_column": "字段指向不明确",
        "invalid_join": "连接条件无效",
        "forbidden_operation": "非只读操作",
        "syntax": "SQL 语法错误",
        "type_mismatch": "字段类型不匹配",
        "timeout": "执行超时",
        "other": "其他执行错误",
    }
    displayed: list[dict[str, object]] = []
    for attempt in trace.get("attempts", []):
        displayed.append(
            {
                "轮次": attempt.get("attempt_number"),
                "状态": "完成" if attempt.get("status") == "succeeded" else "未完成",
                "阶段": stage_labels.get(attempt.get("failure_stage"), "执行完成"),
                "错误类型": error_labels.get(attempt.get("error_type"), "—"),
                "返回行数": attempt.get("row_count"),
                "耗时(ms)": attempt.get("execution_ms"),
            }
        )
    return displayed


def format_display_rows(rows: list[list[object]]) -> list[list[object]]:
    formatted: list[list[object]] = []
    for row in rows:
        display_row: list[object] = []
        for value in row:
            if isinstance(value, float):
                decimals = 2 if abs(value) >= 1000 else 4
                display_row.append(f"{value:,.{decimals}f}")
            else:
                display_row.append(value)
        formatted.append(display_row)
    return formatted
