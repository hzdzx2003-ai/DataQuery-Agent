"""Generate deterministic, fictional commercial-real-estate demo data."""

from __future__ import annotations

import csv
import random
import sqlite3
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "data" / "schema.sql"
OUTPUT_DIR = ROOT / "data" / "generated"
DB_PATH = OUTPUT_DIR / "commercial_real_estate.sqlite3"
SEED = 20260901
AS_OF_DATE = date(2026, 9, 1)


def month_starts(start: date, end: date):
    current = date(start.year, start.month, 1)
    final = date(end.year, end.month, 1)
    while current <= final:
        yield current
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)


def add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def build_properties():
    return [
        ("P001", "澄明广场", "上海", "浦东新区", "shopping_mall", 2972.0, "2018-05-18"),
        ("P002", "云栖中心", "上海", "徐汇区", "office", 3172.0, "2020-09-10"),
        ("P003", "湖滨里", "杭州", "上城区", "community_retail", 3372.0, "2019-11-22"),
        ("P004", "金陵汇", "南京", "建邺区", "shopping_mall", 3572.0, "2017-03-15"),
        ("P005", "平江坊", "苏州", "姑苏区", "community_retail", 3772.0, "2021-06-30"),
        ("P006", "望京新程", "北京", "朝阳区", "office", 3972.0, "2016-12-08"),
    ]


def build_units(properties):
    occupancy_count = {"P001": 7, "P002": 6, "P003": 6, "P004": 5, "P005": 6, "P006": 7}
    unit_types = ["retail", "food_beverage", "retail", "service", "office", "retail", "food_beverage", "office"]
    rows = []
    for property_index, prop in enumerate(properties, start=1):
        property_id = prop[0]
        for unit_index in range(1, 9):
            area = 180 + property_index * 25 + unit_index * 37
            rows.append(
                (
                    f"U{property_index:02d}{unit_index:02d}",
                    property_id,
                    f"{unit_index // 4 + 1}F-{unit_index:02d}",
                    unit_index // 4 + 1,
                    unit_types[unit_index - 1],
                    float(area),
                    "occupied" if unit_index <= occupancy_count[property_id] else "vacant",
                )
            )
    return rows


def build_tenants_and_leases(units):
    prefixes = ["青禾", "远山", "白露", "星港", "木棉", "知味", "拾光", "澜庭", "青岚", "简川"]
    suffixes = ["餐饮", "科技", "零售", "生活", "设计", "咖啡", "健康", "教育"]
    industries = ["餐饮", "科技服务", "服饰零售", "生活服务", "专业服务", "咖啡茶饮", "健康管理", "教育培训"]
    cities = ["上海", "杭州", "南京", "苏州", "北京"]
    tenants = []
    leases = []
    tenant_counter = 0
    lease_counter = 0
    shared_tenant_id = None

    def create_tenant(area: float) -> str:
        nonlocal tenant_counter
        tenant_counter += 1
        tenant_id = f"T{tenant_counter:03d}"
        name = (
            f"{prefixes[(tenant_counter - 1) % len(prefixes)]}"
            f"{suffixes[((tenant_counter - 1) // len(prefixes)) % len(suffixes)]}"
            f"{tenant_counter:02d}号店"
        )
        industry = industries[(tenant_counter - 1) % len(industries)]
        tier = "anchor" if area >= 500 else ("standard" if tenant_counter % 4 else "emerging")
        tenants.append((tenant_id, name, industry, tier, cities[(tenant_counter - 1) % len(cities)]))
        return tenant_id

    def add_lease(unit, tenant_id: str, start_date: date, end_date: date) -> None:
        nonlocal lease_counter
        lease_counter += 1
        unit_id, property_id, _, _, _, area, _ = unit
        property_number = int(property_id[1:])
        unit_number = int(unit_id[-2:])
        daily_rate = 3.2 + property_number * 0.35 + (unit_number % 3) * 0.28
        monthly_rent = round(area * daily_rate * 30, 2)
        status = "active" if start_date <= AS_OF_DATE <= end_date else "expired"
        leases.append(
            (
                f"L{lease_counter:03d}",
                unit_id,
                tenant_id,
                start_date.isoformat(),
                end_date.isoformat(),
                monthly_rent,
                round(monthly_rent * 3, 2),
                status,
            )
        )

    occupied_units = [row for row in units if row[-1] == "occupied"]
    for index, unit in enumerate(occupied_units, start=1):
        unit_id, property_id, _, _, _, area, _ = unit
        property_number = int(property_id[1:])
        unit_number = int(unit_id[-2:])

        if unit_id == "U0101":
            former_tenant_id = create_tenant(area)
            add_lease(unit, former_tenant_id, date(2025, 1, 1), date(2026, 3, 31))
            shared_tenant_id = create_tenant(area)
            add_lease(unit, shared_tenant_id, date(2026, 4, 1), date(2026, 9, 30))
            continue

        if unit_id == "U0102":
            tenant_id = shared_tenant_id
        else:
            tenant_id = create_tenant(area)

        start_date = add_months(date(2025, 1, 1), (index + unit_number) % 8)
        if unit_id == "U0501":
            start_date = date(2026, 6, 1)
        if unit_id == "U0201":
            end_date = date(2026, 9, 1)
        elif unit_id == "U0301":
            end_date = date(2026, 11, 30)
        else:
            end_date = date(2027, 12, 31)
        add_lease(unit, tenant_id, start_date, end_date)

    unit_by_id = {unit[0]: unit for unit in units}
    for unit_id, start_date, end_date in (
        ("U0108", date(2025, 1, 1), date(2026, 2, 28)),
        ("U0406", date(2025, 3, 1), date(2025, 12, 31)),
    ):
        unit = unit_by_id[unit_id]
        historical_tenant_id = create_tenant(unit[5])
        add_lease(unit, historical_tenant_id, start_date, end_date)
    return tenants, leases


def build_payments(leases):
    rows = []
    payment_index = 1
    data_end = date(2026, 8, 1)
    for lease_index, lease in enumerate(leases, start=1):
        lease_id = lease[0]
        start = date.fromisoformat(lease[3])
        end = min(date.fromisoformat(lease[4]), date(2026, 8, 31))
        monthly_rent = lease[5]
        for month in month_starts(start, end):
            if month > data_end:
                break
            due_date = date(month.year, month.month, 5)
            marker = (lease_index * 7 + month.year + month.month * 3) % 10
            if marker <= 6:
                amount_paid = monthly_rent
                paid_date = due_date + timedelta(days=marker % 4)
                status = "paid"
            elif marker <= 8:
                amount_paid = round(monthly_rent * (0.45 + (marker - 7) * 0.2), 2)
                paid_date = due_date + timedelta(days=10 + marker)
                status = "partial"
            else:
                amount_paid = 0.0
                paid_date = None
                status = "overdue"
            rows.append(
                (
                    f"RP{payment_index:05d}",
                    lease_id,
                    month.isoformat(),
                    monthly_rent,
                    amount_paid,
                    due_date.isoformat(),
                    paid_date.isoformat() if paid_date else None,
                    status,
                )
            )
            payment_index += 1
    return rows


def build_expenses(properties, rng):
    categories = ["property_management", "utilities", "maintenance", "marketing", "security"]
    category_weights = {
        "property_management": 0.34,
        "utilities": 0.27,
        "maintenance": 0.18,
        "marketing": 0.12,
        "security": 0.09,
    }
    rows = []
    expense_index = 1
    for property_index, prop in enumerate(properties, start=1):
        area = prop[5]
        for month in month_starts(date(2025, 1, 1), date(2026, 8, 1)):
            seasonal = 1.12 if month.month in (7, 8) else (1.06 if month.month in (1, 2) else 1.0)
            monthly_budget = area * (7.4 + property_index * 0.28)
            for category in categories:
                budget = monthly_budget * category_weights[category]
                variance = rng.uniform(0.92, 1.10)
                amount = round(budget * seasonal * variance, 2)
                rows.append(
                    (
                        f"OE{expense_index:05d}",
                        prop[0],
                        month.isoformat(),
                        category,
                        amount,
                        round(budget, 2),
                    )
                )
                expense_index += 1
    return rows


def export_csv(connection: sqlite3.Connection, table: str) -> None:
    cursor = connection.execute(f"SELECT * FROM {table}")
    path = OUTPUT_DIR / f"{table}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([description[0] for description in cursor.description])
        writer.writerows(cursor.fetchall())


def main() -> None:
    rng = random.Random(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    properties = build_properties()
    units = build_units(properties)
    tenants, leases = build_tenants_and_leases(units)
    payments = build_payments(leases)
    expenses = build_expenses(properties, rng)

    connection = sqlite3.connect(DB_PATH)
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.executemany("INSERT INTO properties VALUES (?, ?, ?, ?, ?, ?, ?)", properties)
        connection.executemany("INSERT INTO units VALUES (?, ?, ?, ?, ?, ?, ?)", units)
        connection.executemany("INSERT INTO tenants VALUES (?, ?, ?, ?, ?)", tenants)
        connection.executemany("INSERT INTO leases VALUES (?, ?, ?, ?, ?, ?, ?, ?)", leases)
        connection.executemany("INSERT INTO rent_payments VALUES (?, ?, ?, ?, ?, ?, ?, ?)", payments)
        connection.executemany("INSERT INTO operating_expenses VALUES (?, ?, ?, ?, ?, ?)", expenses)
        connection.commit()
        for table in ("properties", "units", "tenants", "leases", "rent_payments", "operating_expenses"):
            export_csv(connection, table)
    finally:
        connection.close()

    print(f"Generated {DB_PATH}")
    print(
        f"Rows: properties={len(properties)}, units={len(units)}, tenants={len(tenants)}, "
        f"leases={len(leases)}, rent_payments={len(payments)}, operating_expenses={len(expenses)}"
    )


if __name__ == "__main__":
    main()
