"""Create the version manifest that freezes the evaluation case set."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evaluation" / "cases.json"
MANIFEST_PATH = ROOT / "evaluation" / "manifest.json"


def main() -> None:
    raw = CASES_PATH.read_bytes()
    cases = json.loads(raw.decode("utf-8"))
    manifest = {
        "version": "2.0.1",
        "frozen_on": "2026-09-22",
        "cases_sha256": hashlib.sha256(raw).hexdigest(),
        "case_count": len(cases),
        "splits": dict(sorted(Counter(case["split"] for case in cases).items())),
        "expected_actions": dict(sorted(Counter(case["expected_action"] for case in cases).items())),
        "supersedes": "2.0.0 (development Gold projection corrected; holdout unchanged)",
        "policy": "Any case-content change requires a new semantic version and a documented reason. Holdout cases must not be used for implementation tuning.",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen evaluation {manifest['version']}: {manifest['cases_sha256']}")


if __name__ == "__main__":
    main()
