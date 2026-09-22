from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import (  # noqa: E402
    JsonTraceStore,
    OpenAICompatibleClient,
    QueryPipeline,
    QueryRouter,
    QwenSqlGenerator,
    ReadOnlySqlGuard,
    load_env_file,
)


def normalized_rows(rows: list[list[object]] | tuple[tuple[object, ...], ...], decimals: int) -> list[list[object]]:
    return [
        [round(value, decimals) if isinstance(value, float) else value for value in row]
        for row in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 3 on executable development cases only.")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--case-id", action="append", help="Optional development case id; repeatable")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation" / "results" / "phase3-development-live.json",
    )
    args = parser.parse_args()
    load_env_file(args.env_file)

    cases = json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    executable = [
        case
        for case in cases
        if case["split"] == "development"
        and case["expected_action"] in {"execute", "execute_with_disclosure"}
    ]
    if args.case_id:
        requested = set(args.case_id)
        selected = [case for case in executable if case["id"] in requested]
        missing = requested - {case["id"] for case in selected}
        if missing:
            raise SystemExit(f"Only executable development case ids are allowed: {sorted(missing)}")
    else:
        selected = executable
    if not selected:
        raise SystemExit("No executable development cases selected")

    router = QueryRouter.from_project_root(ROOT)
    guard = ReadOnlySqlGuard(ROOT / "data" / "generated" / "commercial_real_estate.sqlite3")
    generator = QwenSqlGenerator(OpenAICompatibleClient.from_environment(), ROOT)
    pipeline = QueryPipeline(router, generator, guard, max_attempts=3)
    trace_store = JsonTraceStore(ROOT / "evaluation" / "results" / "phase3-traces")
    catalog = json.loads((ROOT / "data" / "metric_catalog.json").read_text(encoding="utf-8"))
    metrics = {metric["id"]: metric for metric in catalog["metrics"]}
    results: list[dict[str, object]] = []

    for case in selected:
        run = pipeline.run(case["question"])
        trace_path = trace_store.save(case["id"], run)
        comparison: bool | None = None
        if run.status == "succeeded":
            _, gold_rows = guard.execute(case["gold_sql"])
            decimals = max(
                (int(metrics[item].get("result_decimals", 6)) for item in run.route.metric_ids),
                default=6,
            )
            comparison = normalized_rows(run.rows, decimals) == normalized_rows(gold_rows, decimals)
        results.append(
            {
                "case_id": case["id"],
                "question": case["question"],
                "status": run.status,
                "attempt_count": len(run.attempts),
                "recovered": run.recovered,
                "row_count": len(run.rows),
                "strict_row_match": comparison,
                "trace_file": trace_path.relative_to(ROOT).as_posix(),
            }
        )
        print(
            f"{case['id']}: status={run.status}, attempts={len(run.attempts)}, "
            f"rows={len(run.rows)}, strict_match={comparison}"
        )

    artifact = {
        "phase": "3-development-live",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "executable development cases only",
        "holdout_accessed": False,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved sanitized result: {args.output}")


if __name__ == "__main__":
    main()
