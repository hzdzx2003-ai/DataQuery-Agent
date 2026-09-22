from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import (  # noqa: E402
    OpenAICompatibleClient,
    QueryRouter,
    ReadOnlySqlGuard,
    load_env_file,
    require_executable,
)
from dataquery_agent.model_client import parse_json_object  # noqa: E402


CASE_IDS = ("D2-001", "D2-004")


def normalized_rows(rows: list[tuple[object, ...]], decimals: int) -> list[list[object]]:
    return [[round(value, decimals) if isinstance(value, float) else value for value in row] for row in rows]


def metric_context(catalog: dict[str, object], metric_ids: tuple[str, ...]) -> list[dict[str, object]]:
    return [metric for metric in catalog["metrics"] if metric["id"] in metric_ids]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the two-case bounded Phase 2B smoke test.")
    parser.add_argument("--env-file", type=Path, help="Private env file; values are never written to results")
    parser.add_argument(
        "--case-id",
        action="append",
        choices=CASE_IDS,
        help="Run only a named smoke case; may be repeated. Defaults to both cases.",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results" / "phase2b-smoke.json")
    args = parser.parse_args()
    if args.env_file:
        load_env_file(args.env_file)

    cases = json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    selected_ids = tuple(args.case_id or CASE_IDS)
    selected = [next(case for case in cases if case["id"] == case_id) for case_id in selected_ids]
    if any(case["split"] != "development" for case in selected):
        raise SystemExit("Smoke test may run development cases only")

    schema = (ROOT / "data" / "schema.sql").read_text(encoding="utf-8")
    catalog = json.loads((ROOT / "data" / "metric_catalog.json").read_text(encoding="utf-8"))
    router = QueryRouter.from_project_root(ROOT)
    guard = ReadOnlySqlGuard(ROOT / "data" / "generated" / "commercial_real_estate.sqlite3")
    client = OpenAICompatibleClient.from_environment()
    results: list[dict[str, object]] = []

    system = (
        "你是商业地产数据分析助手。只为 SQLite 生成一条只读 SELECT 或 WITH 查询。"
        "只能使用给定 Schema 和指标定义，不得编造表、字段或指标，不得使用 SELECT *。"
        "只返回 JSON 对象，格式为 {\"sql\":\"...\",\"summary\":\"一句中文口径说明\"}。"
    )
    for case in selected:
        decision = require_executable(router.route(case["question"]))
        user = json.dumps(
            {
                "question": case["question"],
                "fixed_as_of_date": catalog["as_of_date"],
                "field_conventions": {
                    "date_storage": "所有日期字段使用 YYYY-MM-DD 文本格式",
                    "month_storage": "billing_month 与 expense_month 也使用每月第一天的 YYYY-MM-DD，例如 2026-08-01",
                    "money": "金额为人民币数值",
                },
                "route": decision.to_dict(),
                "relevant_metrics": metric_context(catalog, decision.metric_ids),
                "schema": schema,
            },
            ensure_ascii=False,
        )
        response = client.chat(system, user, max_tokens=1200)
        parsed = parse_json_object(response.content)
        sql = str(parsed.get("sql", "")).strip()
        columns, rows = guard.execute(sql)
        gold_columns, gold_rows = guard.execute(case["gold_sql"])
        relevant_metrics = metric_context(catalog, decision.metric_ids)
        decimals = max((int(metric.get("result_decimals", 6)) for metric in relevant_metrics), default=6)
        result_match = normalized_rows(rows, decimals) == normalized_rows(gold_rows, decimals)
        results.append(
            {
                "case_id": case["id"],
                "question": case["question"],
                "route_action": decision.action,
                "generated_sql": sql,
                "summary": parsed.get("summary", ""),
                "columns": columns,
                "row_count": len(rows),
                "gold_columns": gold_columns,
                "gold_row_count": len(gold_rows),
                "strict_row_match": result_match,
                "numeric_comparison_decimals": decimals,
                "model": response.model,
                "latency_ms": response.latency_ms,
                "usage": response.to_dict()["usage"],
                "disclosures": decision.disclosures,
            }
        )

    artifact = {
        "phase": "2B-smoke",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_ids": list(selected_ids),
        "request_count": len(results),
        "total_tokens": sum(item["usage"]["total_tokens"] for item in results),
        "all_strict_row_match": all(item["strict_row_match"] for item in results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Phase 2B smoke requests: {artifact['request_count']}")
    print(f"Total tokens: {artifact['total_tokens']}")
    for item in results:
        print(
            f"{item['case_id']}: action={item['route_action']}, rows={item['row_count']}, "
            f"strict_match={item['strict_row_match']}, latency_ms={item['latency_ms']}, "
            f"tokens={item['usage']['total_tokens']}"
        )
    if not artifact["all_strict_row_match"]:
        raise SystemExit("Smoke test completed, but at least one result did not match Gold SQL")
    print(f"Saved sanitized result: {args.output}")


if __name__ == "__main__":
    main()
