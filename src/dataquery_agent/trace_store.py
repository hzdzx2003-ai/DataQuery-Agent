from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .pipeline import QueryRun


class JsonTraceStore:
    """Persist only the public QueryRun trace as UTF-8 JSON."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(self, run_id: str, run: QueryRun) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / f"{run_id}.json"
        payload = json.dumps(run.to_dict(), ensure_ascii=False, indent=2)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{run_id}-", suffix=".tmp", dir=self.directory, text=True
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as temporary:
                temporary.write(payload)
                temporary.write("\n")
            Path(temporary_name).replace(destination)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        return destination
