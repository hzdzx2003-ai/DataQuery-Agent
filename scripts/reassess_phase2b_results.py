from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import ReadOnlySqlGuard  # noqa: E402
from run_phase2b_smoke import metric_context, normalized_rows  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Reassess saved smoke SQL without another model call.")
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    cases = {
        case["id"]: case
        for case in json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    }
    catalog = json.loads((ROOT / "data" / "metric_catalog.json").read_text(encoding="utf-8"))
    guard = ReadOnlySqlGuard(ROOT / "data" / "generated" / "commercial_real_estate.sqlite3")

    for result in artifact["results"]:
        case = cases[result["case_id"]]
        _, rows = guard.execute(result["generated_sql"])
        _, gold_rows = guard.execute(case["gold_sql"])
        metrics = metric_context(catalog, tuple(case.get("metric_ids", [])))
        decimals = max((int(metric.get("result_decimals", 6)) for metric in metrics), default=6)
        result["strict_row_match"] = normalized_rows(rows, decimals) == normalized_rows(gold_rows, decimals)
        result["numeric_comparison_decimals"] = decimals
    artifact["all_strict_row_match"] = all(item["strict_row_match"] for item in artifact["results"])
    args.artifact.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Reassessed {args.artifact}: all_strict_row_match={artifact['all_strict_row_match']}")


if __name__ == "__main__":
    main()
