"""OV2-F.2D — Migration: Create ops.driver_day_slice_fact (additive, no DROP)
Usage: python -m scripts.migrate_driver_day_slice_fact"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

TABLE = "ops.driver_day_slice_fact"
SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id BIGSERIAL PRIMARY KEY,
    activity_date DATE NOT NULL,
    country TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    park_id TEXT NOT NULL DEFAULT '',
    business_slice_name TEXT NOT NULL DEFAULT '',
    driver_id TEXT NOT NULL DEFAULT '',
    completed_trips INTEGER NOT NULL DEFAULT 0,
    cancelled_trips INTEGER NOT NULL DEFAULT 0,
    total_trips INTEGER NOT NULL DEFAULT 0,
    completed_flag BOOLEAN NOT NULL DEFAULT FALSE,
    cancel_only_flag BOOLEAN NOT NULL DEFAULT FALSE,
    empty_supply_flag BOOLEAN NOT NULL DEFAULT FALSE,
    first_completed_at TIMESTAMPTZ,
    last_completed_at TIMESTAMPTZ,
    source_system TEXT NOT NULL DEFAULT 'CT_TRIPS_2026',
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    confidence TEXT NOT NULL DEFAULT 'HIGH',
    warning_codes TEXT[] NOT NULL DEFAULT '{{}}'
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_dds_pk
    ON {TABLE} (activity_date, country, city, park_id, business_slice_name, driver_id);

CREATE INDEX IF NOT EXISTS ix_dds_date ON {TABLE} (activity_date);
CREATE INDEX IF NOT EXISTS ix_dds_country_city ON {TABLE} (country, city);
CREATE INDEX IF NOT EXISTS ix_dds_slice ON {TABLE} (business_slice_name);
CREATE INDEX IF NOT EXISTS ix_dds_driver ON {TABLE} (driver_id, activity_date);
CREATE INDEX IF NOT EXISTS ix_dds_park ON {TABLE} (park_id, activity_date);
"""

def main():
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS ops")
            cur.execute(SQL)
            conn.commit()
            print(f"Table {TABLE} created/verified successfully")
            cur.execute(f"SELECT count(*) FROM {TABLE}")
            print(f"Existing rows: {cur.fetchone()[0]}")
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {e}")
            return 1
        finally:
            cur.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
