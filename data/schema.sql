PRAGMA foreign_keys = ON;

CREATE TABLE properties (
    property_id TEXT PRIMARY KEY,
    property_name TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    district TEXT NOT NULL,
    property_type TEXT NOT NULL CHECK (property_type IN ('shopping_mall', 'office', 'community_retail')),
    gross_leasable_area_sqm REAL NOT NULL CHECK (gross_leasable_area_sqm > 0),
    opening_date TEXT NOT NULL
);

CREATE TABLE units (
    unit_id TEXT PRIMARY KEY,
    property_id TEXT NOT NULL REFERENCES properties(property_id),
    unit_number TEXT NOT NULL,
    floor INTEGER NOT NULL,
    unit_type TEXT NOT NULL CHECK (unit_type IN ('retail', 'office', 'food_beverage', 'service')),
    leasable_area_sqm REAL NOT NULL CHECK (leasable_area_sqm > 0),
    status TEXT NOT NULL CHECK (status IN ('occupied', 'vacant')),
    UNIQUE (property_id, unit_number)
);

CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY,
    tenant_name TEXT NOT NULL UNIQUE,
    industry TEXT NOT NULL,
    tenant_tier TEXT NOT NULL CHECK (tenant_tier IN ('anchor', 'standard', 'emerging')),
    registered_city TEXT NOT NULL
);

CREATE TABLE leases (
    lease_id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL REFERENCES units(unit_id),
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    lease_start_date TEXT NOT NULL,
    lease_end_date TEXT NOT NULL,
    monthly_base_rent REAL NOT NULL CHECK (monthly_base_rent > 0),
    deposit_amount REAL NOT NULL CHECK (deposit_amount >= 0),
    lease_status TEXT NOT NULL CHECK (lease_status IN ('active', 'expired')),
    CHECK (lease_end_date >= lease_start_date)
);

CREATE TABLE rent_payments (
    payment_id TEXT PRIMARY KEY,
    lease_id TEXT NOT NULL REFERENCES leases(lease_id),
    billing_month TEXT NOT NULL,
    amount_due REAL NOT NULL CHECK (amount_due >= 0),
    amount_paid REAL NOT NULL CHECK (amount_paid >= 0 AND amount_paid <= amount_due),
    due_date TEXT NOT NULL,
    paid_date TEXT,
    payment_status TEXT NOT NULL CHECK (payment_status IN ('paid', 'partial', 'overdue')),
    UNIQUE (lease_id, billing_month)
);

CREATE TABLE operating_expenses (
    expense_id TEXT PRIMARY KEY,
    property_id TEXT NOT NULL REFERENCES properties(property_id),
    expense_month TEXT NOT NULL,
    expense_category TEXT NOT NULL CHECK (expense_category IN ('property_management', 'utilities', 'maintenance', 'marketing', 'security')),
    amount REAL NOT NULL CHECK (amount >= 0),
    budget_amount REAL NOT NULL CHECK (budget_amount >= 0),
    UNIQUE (property_id, expense_month, expense_category)
);

