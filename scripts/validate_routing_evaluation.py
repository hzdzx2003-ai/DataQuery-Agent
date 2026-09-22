from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import QueryRouter  # noqa: E402


def collect_trigger_terms(value: object, key: str = "") -> list[str]:
    terms: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            terms.extend(collect_trigger_terms(child, child_key))
    elif isinstance(value, list):
        if key in {"terms", "subject_terms", "severity_terms", "degree_terms"}:
            terms.extend(item for item in value if isinstance(item, str))
        else:
            for child in value:
                terms.extend(collect_trigger_terms(child, key))
    return terms


def main() -> None:
    cases = json.loads((ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
    router = QueryRouter.from_project_root(ROOT)
    development = [case for case in cases if case["split"] == "development"]
    holdout = [case for case in cases if case["split"] == "holdout"]

    triggered = {router.route(case["question"]).reason_code for case in development}
    required_rules = {
        rule["id"] for rule in router.policy["rejection_rules"]
    } | {
        rule_id
        for rule_id in router.policy["clarification_rules"]
        if rule_id not in {"empty_question", "unknown_request"}
    }
    missing = sorted(required_rules - triggered)
    if missing:
        raise SystemExit(f"Development set does not exercise rules: {missing}")

    dev_text = "\n".join(case["question"].lower().replace(" ", "") for case in development)
    holdout_text = "\n".join(case["question"].lower().replace(" ", "") for case in holdout)
    suspicious = sorted(
        term
        for term in set(collect_trigger_terms(router.policy))
        if len(term) >= 6 and term.lower().replace(" ", "") in holdout_text
        and term.lower().replace(" ", "") not in dev_text
    )
    if suspicious:
        raise SystemExit(f"Long trigger phrases appear only in holdout: {suspicious}")

    print(f"Routing evaluation structure passed: development={len(development)}, holdout={len(holdout)}")
    print(f"Development rule coverage: {len(required_rules)}/{len(required_rules)}")


if __name__ == "__main__":
    main()
