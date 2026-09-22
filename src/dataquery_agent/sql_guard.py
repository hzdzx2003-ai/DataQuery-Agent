from __future__ import annotations

import re
import sqlite3
from pathlib import Path


class SqlGuardError(ValueError):
    pass


class ReadOnlySqlGuard:
    """Validate and execute a single read-only SQLite query with defense in depth."""

    FORBIDDEN = re.compile(
        r"\b(attach|detach|pragma|insert|update|delete|drop|alter|create|replace|"
        r"vacuum|reindex|analyze|transaction|commit|rollback|savepoint|release)\b",
        re.IGNORECASE,
    )
    COMMENT = re.compile(r"--|/\*|\*/")

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()

    def validate(self, sql: str) -> str:
        candidate = sql.strip()
        if not candidate:
            raise SqlGuardError("SQL is empty")
        if self.COMMENT.search(candidate):
            raise SqlGuardError("SQL comments are not allowed")
        body = candidate[:-1].rstrip() if candidate.endswith(";") else candidate
        if ";" in body:
            raise SqlGuardError("Only one SQL statement is allowed")
        if not re.match(r"^(select|with)\b", body, re.IGNORECASE):
            raise SqlGuardError("Only SELECT or WITH queries are allowed")
        forbidden = self.FORBIDDEN.search(body)
        if forbidden:
            raise SqlGuardError(f"Forbidden SQL keyword: {forbidden.group(1).upper()}")
        return body

    def connect(self) -> sqlite3.Connection:
        uri = self.database_path.as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only = ON")
        connection.set_authorizer(self._authorizer)
        return connection

    def execute(self, sql: str) -> tuple[list[str], list[tuple[object, ...]]]:
        validated = self.validate(sql)
        connection = self.connect()
        try:
            cursor = connection.execute(validated)
            columns = [item[0] for item in cursor.description or []]
            return columns, cursor.fetchall()
        except sqlite3.DatabaseError as exc:
            raise SqlGuardError(f"Read-only query rejected: {exc}") from exc
        finally:
            connection.close()

    @staticmethod
    def _authorizer(action: int, _arg1: str | None, _arg2: str | None, _db: str | None, _source: str | None) -> int:
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            getattr(sqlite3, "SQLITE_RECURSIVE", -1),
        }
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY
