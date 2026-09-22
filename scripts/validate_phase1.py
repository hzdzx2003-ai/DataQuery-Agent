"""Validate Phase 1 data constraints and executable evaluation cases."""

from __future__ import annotations

import json
import hashlib
import sqlite3
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "generated" / "commercial_real_estate.sqlite3"
CASES_PATH = ROOT / "evaluation" / "cases.json"
METRICS_PATH = ROOT / "data" / "metric_catalog.json"
MANIFEST_PATH = ROOT / "evaluation" / "manifest.json"


class ValidationError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def scalar(connection: sqlite3.Connection, sql: str):
    return connection.execute(sql).fetchone()[0]


def validate_database(connection: sqlite3.Connection) -> dict[str, int]:
    catalog = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    as_of_date = catalog["as_of_date"]
    expected_minimums = {
        "properties": 6,
        "units": 48,
        "tenants": 30,
        "leases": 30,
        "rent_payments": 400,
        "operating_expenses": 500,
    }
    counts = {}
    for table, minimum in expected_minimums.items():
        count = scalar(connection, f"SELECT COUNT(*) FROM {table}")
        require(count >= minimum, f"{table}: expected at least {minimum} rows, got {count}")
        counts[table] = count

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    require(not foreign_key_errors, f"Foreign key failures: {foreign_key_errors[:5]}")

    area_mismatches = connection.execute(
        """
        SELECT p.property_id, SUM(u.leasable_area_sqm), p.gross_leasable_area_sqm
        FROM properties p JOIN units u ON p.property_id = u.property_id
        GROUP BY p.property_id
        HAVING ABS(SUM(u.leasable_area_sqm) - p.gross_leasable_area_sqm) > 0.001
        """
    ).fetchall()
    require(not area_mismatches, f"Unit inventory must exactly reconcile to project GLA: {area_mismatches}")

    overlaps = connection.execute(
        """
        SELECT a.lease_id, b.lease_id
        FROM leases a JOIN leases b
          ON a.unit_id = b.unit_id AND a.lease_id < b.lease_id
        WHERE a.lease_start_date <= b.lease_end_date
          AND b.lease_start_date <= a.lease_end_date
        """
    ).fetchall()
    require(not overlaps, f"Overlapping leases found: {overlaps[:5]}")

    status_mismatches = connection.execute(
        """
        SELECT u.unit_id, u.status
        FROM units u
        WHERE (u.status = 'occupied') != EXISTS (
          SELECT 1 FROM leases l
          WHERE l.unit_id = u.unit_id
            AND l.lease_start_date <= :as_of_date
            AND l.lease_end_date >= :as_of_date
        )
        """,
        {"as_of_date": as_of_date},
    ).fetchall()
    require(not status_mismatches, f"Unit status disagrees with active leases: {status_mismatches[:5]}")

    invalid_payment_months = connection.execute(
        """
        SELECT rp.payment_id
        FROM rent_payments rp JOIN leases l ON rp.lease_id = l.lease_id
        WHERE rp.billing_month < substr(l.lease_start_date, 1, 7) || '-01'
           OR rp.billing_month > substr(l.lease_end_date, 1, 7) || '-01'
        """
    ).fetchall()
    require(not invalid_payment_months, f"Payments outside lease dates: {invalid_payment_months[:5]}")

    invalid_payment_status = connection.execute(
        """
        SELECT payment_id, amount_due, amount_paid, payment_status
        FROM rent_payments
        WHERE (amount_paid = amount_due AND payment_status <> 'paid')
           OR (amount_paid = 0 AND payment_status <> 'overdue')
           OR (amount_paid > 0 AND amount_paid < amount_due AND payment_status <> 'partial')
        """
    ).fetchall()
    require(not invalid_payment_status, f"Payment status mismatch: {invalid_payment_status[:5]}")

    invalid_payment_dates = connection.execute(
        """
        SELECT payment_id, due_date, paid_date, payment_status
        FROM rent_payments
        WHERE (payment_status IN ('paid', 'partial') AND paid_date IS NULL)
           OR (payment_status = 'overdue' AND paid_date IS NOT NULL)
           OR (paid_date IS NOT NULL AND paid_date < due_date)
           OR (paid_date IS NOT NULL AND paid_date >= :as_of_date)
        """,
        {"as_of_date": as_of_date},
    ).fetchall()
    require(not invalid_payment_dates, f"Payment date/status mismatch: {invalid_payment_dates[:5]}")

    expired_lease_count = scalar(connection, "SELECT COUNT(*) FROM leases WHERE lease_status = 'expired'")
    require(expired_lease_count >= 3, f"Expected at least 3 expired leases, got {expired_lease_count}")

    starts_in_2026 = scalar(
        connection,
        "SELECT COUNT(*) FROM leases WHERE lease_start_date >= '2026-01-01' AND lease_start_date < '2027-01-01'",
    )
    require(starts_in_2026 >= 1, "Expected at least one lease starting in 2026")

    boundary_lease_count = scalar(
        connection,
        "SELECT COUNT(*) FROM leases WHERE lease_end_date IN ('2026-09-01', '2026-11-30')",
    )
    require(boundary_lease_count == 2, f"Expected two boundary leases, got {boundary_lease_count}")

    multi_lease_units = scalar(
        connection,
        "SELECT COUNT(*) FROM (SELECT unit_id FROM leases GROUP BY unit_id HAVING COUNT(*) > 1)",
    )
    require(multi_lease_units >= 1, "Expected at least one unit with sequential leases")

    multi_unit_tenants = scalar(
        connection,
        "SELECT COUNT(*) FROM (SELECT tenant_id FROM leases GROUP BY tenant_id HAVING COUNT(DISTINCT unit_id) > 1)",
    )
    require(multi_unit_tenants >= 1, "Expected at least one tenant leasing multiple units")

    snapshot_area = scalar(connection, "SELECT SUM(leasable_area_sqm) FROM units WHERE status = 'occupied'")
    historical_area = scalar(
        connection,
        """
        SELECT SUM(u.leasable_area_sqm)
        FROM units u
        WHERE EXISTS (
          SELECT 1 FROM leases l
          WHERE l.unit_id = u.unit_id
            AND l.lease_start_date <= '2026-01-01'
            AND l.lease_end_date >= '2026-01-01'
        )
        """,
    )
    require(
        abs(snapshot_area - historical_area) > 0.001,
        "Historical occupancy must differ from the current unit-status snapshot",
    )

    negative_expenses = scalar(
        connection,
        "SELECT COUNT(*) FROM operating_expenses WHERE amount < 0 OR budget_amount < 0",
    )
    require(negative_expenses == 0, "Negative expense or budget found")
    return counts


def validate_evaluation(connection: sqlite3.Connection) -> tuple[Counter, Counter, dict[str, int]]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases_sha256 = hashlib.sha256(CASES_PATH.read_bytes()).hexdigest()
    require(manifest["cases_sha256"] == cases_sha256, "Evaluation cases changed after freeze; create a new version")
    metric_ids = {metric["id"] for metric in metrics["metrics"]}
    require(len(cases) == manifest["case_count"], f"Manifest expects {manifest['case_count']} cases, got {len(cases)}")
    require(len({case['id'] for case in cases}) == len(cases), "Evaluation IDs must be unique")

    actions = Counter(case["expected_action"] for case in cases)
    require(actions == Counter(manifest["expected_actions"]), f"Unexpected action mix: {actions}")
    splits = Counter(case.get("split") for case in cases)
    require(splits == Counter(manifest["splits"]), f"Unexpected split: {splits}")

    row_counts = {}
    for case in cases:
        unknown_metrics = set(case.get("metric_ids", [])) - metric_ids
        require(not unknown_metrics, f"{case['id']} uses unknown metrics: {sorted(unknown_metrics)}")
        action = case["expected_action"]
        if action in {"execute", "execute_with_disclosure"}:
            sql = case.get("gold_sql", "").strip()
            require(sql.upper().startswith(("SELECT", "WITH")), f"{case['id']} Gold SQL must be read-only")
            rows = connection.execute(sql).fetchall()
            if case.get("expected_empty"):
                require(not rows, f"{case['id']} expected an empty Gold result, got {len(rows)} rows")
                require(case.get("expected_message_contains"), f"{case['id']} needs empty-result user message cues")
            else:
                require(rows, f"{case['id']} Gold SQL returned no rows")
            if action == "execute_with_disclosure":
                require(case.get("expected_disclosure_contains"), f"{case['id']} needs disclosure cues")
            row_counts[case["id"]] = len(rows)
        else:
            require("gold_sql" not in case, f"{case['id']} must not contain Gold SQL")
            require(case.get("expected_message_contains"), f"{case['id']} needs expected response cues")
            if action == "clarify":
                options = case.get("expected_options", [])
                require(len(options) >= 2, f"{case['id']} needs at least two structured clarification options")
                require(
                    all(option.get("id") and option.get("acceptable_terms") for option in options),
                    f"{case['id']} has incomplete clarification options",
                )
    dangerous_write_cases = [
        case
        for case in cases
        if any(token in case["question"] for token in ("删除", "修改", "写入", "清空", "移除"))
    ]
    require(dangerous_write_cases, "At least one dangerous write-operation case is required")
    require(all(case["expected_action"] == "reject" for case in dangerous_write_cases), "Write operations must be rejected")
    return actions, splits, row_counts


def main() -> None:
    require(DB_PATH.exists(), f"Database not found. Run scripts/generate_synthetic_data.py first: {DB_PATH}")
    connection = sqlite3.connect(DB_PATH)
    try:
        counts = validate_database(connection)
        actions, splits, result_rows = validate_evaluation(connection)
    finally:
        connection.close()

    print("Phase 1 validation passed")
    print("Table rows: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
    print("Evaluation mix: " + ", ".join(f"{name}={count}" for name, count in sorted(actions.items())))
    print("Evaluation split: " + ", ".join(f"{name}={count}" for name, count in sorted(splits.items())))
    print("Evaluation version: " + json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["version"])
    print("Gold SQL result rows: " + ", ".join(f"{case_id}={count}" for case_id, count in result_rows.items()))


if __name__ == "__main__":
    main()
