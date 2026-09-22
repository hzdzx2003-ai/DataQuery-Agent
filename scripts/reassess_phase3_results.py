from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import ReadOnlySqlGuard  # noqa: E402


def normalized(rows: list[list[object]], decimals: int) -> list[list[object]]:
    return [
        [round(value, decimals) if isinstance(value, float) else value for value in row]
        for row in rows
    ]


def main() -> None:
    result_path = ROOT / "evaluation" / "results" / "phase3-development-live.json"
    artifact = json.loads(result_path.read_text(encoding="utf-8"))
    cases = {
        case["id"]: case
        for case in json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    }
    manifest = json.loads((ROOT / "evaluation" / "manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "data" / "metric_catalog.json").read_text(encoding="utf-8"))
    metrics = {metric["id"]: metric for metric in catalog["metrics"]}
    guard = ReadOnlySqlGuard(ROOT / "data" / "generated" / "commercial_real_estate.sqlite3")

    for item in artifact["results"]:
        case = cases[item["case_id"]]
        trace = json.loads((ROOT / item["trace_file"]).read_text(encoding="utf-8"))
        if trace["status"] != "succeeded":
            item["strict_row_match"] = None
            continue
        _, gold_rows = guard.execute(case["gold_sql"])
        decimals = max(
            (int(metrics[metric_id].get("result_decimals", 6)) for metric_id in trace["route"]["metric_ids"]),
            default=6,
        )
        item["strict_row_match"] = normalized(trace["rows"], decimals) == normalized(
            [list(row) for row in gold_rows], decimals
        )

    artifact["evaluation_version"] = manifest["version"]
    artifact["reassessed_at"] = datetime.now(timezone.utc).isoformat()
    result_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in artifact["results"]:
        print(f"{item['case_id']}: strict_match={item['strict_row_match']}")


if __name__ == "__main__":
    main()
