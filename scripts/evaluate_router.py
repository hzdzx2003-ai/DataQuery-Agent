from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import QueryRouter  # noqa: E402


def main() -> None:
    cases = json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    development_cases = [case for case in cases if case["split"] == "development"]
    router = QueryRouter.from_project_root(ROOT)
    failures: list[str] = []
    predicted = Counter()

    for case in development_cases:
        decision = router.route(case["question"])
        predicted[decision.action] += 1
        if decision.action != case["expected_action"]:
            failures.append(
                f"{case['id']}: expected {case['expected_action']}, got "
                f"{decision.action} ({decision.reason_code})"
            )
            continue
        expected_metrics = tuple(case.get("metric_ids", []))
        if expected_metrics and set(expected_metrics) != set(decision.metric_ids):
            failures.append(
                f"{case['id']}: expected metrics {expected_metrics}, got {decision.metric_ids}"
            )
        for cue in case.get("expected_message_contains", []):
            option_text = " ".join(option.label for option in decision.options)
            if cue not in f"{decision.message} {option_text}":
                failures.append(f"{case['id']}: missing message cue {cue!r}")
        disclosure_text = " ".join(decision.disclosures)
        for cue in case.get("expected_disclosure_contains", []):
            if cue.lower().replace(" ", "") not in disclosure_text.lower().replace(" ", ""):
                failures.append(f"{case['id']}: missing disclosure cue {cue!r}")

    print(f"Development cases evaluated: {len(development_cases)}")
    print(f"Predicted actions: {dict(sorted(predicted.items()))}")
    if failures:
        print("Failures:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("Phase 2A offline routing evaluation passed.")


if __name__ == "__main__":
    main()
