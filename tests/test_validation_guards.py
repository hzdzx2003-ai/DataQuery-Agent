from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_synthetic_data  # noqa: E402
import validate_phase1  # noqa: E402


class ValidationGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        generate_synthetic_data.main()

    def copied_connection(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "test.sqlite3"
        shutil.copy2(generate_synthetic_data.DB_PATH, db_path)
        connection = sqlite3.connect(db_path)
        return temp_dir, connection

    def test_overlapping_lease_is_rejected(self) -> None:
        temp_dir, connection = self.copied_connection()
        try:
            connection.execute(
                """
                INSERT INTO leases VALUES (
                  'L999', 'U0101', 'T001', '2026-01-01', '2026-02-28',
                  10000, 30000, 'expired'
                )
                """
            )
            connection.commit()
            with self.assertRaisesRegex(validate_phase1.ValidationError, "Overlapping leases"):
                validate_phase1.validate_database(connection)
        finally:
            connection.close()
            temp_dir.cleanup()

    def test_payment_status_mismatch_is_rejected(self) -> None:
        temp_dir, connection = self.copied_connection()
        try:
            payment_id = connection.execute(
                "SELECT payment_id FROM rent_payments WHERE amount_paid < amount_due LIMIT 1"
            ).fetchone()[0]
            connection.execute(
                "UPDATE rent_payments SET payment_status = 'paid' WHERE payment_id = ?",
                (payment_id,),
            )
            connection.commit()
            with self.assertRaisesRegex(validate_phase1.ValidationError, "Payment status mismatch"):
                validate_phase1.validate_database(connection)
        finally:
            connection.close()
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()

