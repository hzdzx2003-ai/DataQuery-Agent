from __future__ import annotations

import sys
import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import ReadOnlySqlGuard, SqlGuardError  # noqa: E402


class SqlGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guard = ReadOnlySqlGuard(ROOT / "data" / "generated" / "commercial_real_estate.sqlite3")

    def test_select_and_cte_are_allowed(self) -> None:
        self.assertEqual("SELECT 1", self.guard.validate("SELECT 1;"))
        self.guard.validate("WITH x AS (SELECT 1 AS n) SELECT n FROM x")

    def test_writes_and_management_statements_are_rejected(self) -> None:
        blocked = [
            "DELETE FROM leases",
            "UPDATE leases SET lease_status='expired'",
            "INSERT INTO leases SELECT * FROM leases",
            "DROP TABLE leases",
            "ATTACH DATABASE 'x.db' AS x",
            "PRAGMA table_info(leases)",
            "WITH x AS (SELECT 1) DELETE FROM leases",
        ]
        for sql in blocked:
            with self.subTest(sql=sql), self.assertRaises(SqlGuardError):
                self.guard.validate(sql)

    def test_multiple_statements_and_comments_are_rejected(self) -> None:
        for sql in ("SELECT 1; DELETE FROM leases", "SELECT 1 -- hidden", "SELECT /*x*/ 1"):
            with self.subTest(sql=sql), self.assertRaises(SqlGuardError):
                self.guard.validate(sql)

    def test_database_connection_is_read_only(self) -> None:
        connection = self.guard.connect()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute("DELETE FROM leases")
        finally:
            connection.close()

    def test_safe_query_executes(self) -> None:
        columns, rows = self.guard.execute("SELECT COUNT(*) AS count FROM properties")
        self.assertEqual(["count"], columns)
        self.assertEqual(6, rows[0][0])


if __name__ == "__main__":
    unittest.main()
