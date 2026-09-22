from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import QueryRouter  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run the offline Phase 2A query router.")
    parser.add_argument("question", help="Chinese business question to classify")
    args = parser.parse_args()
    decision = QueryRouter.from_project_root(ROOT).route(args.question)
    print(json.dumps(decision.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
