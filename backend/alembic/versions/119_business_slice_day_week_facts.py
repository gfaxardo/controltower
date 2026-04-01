"""
119 — Tablas fact agregadas para Business Slice daily y weekly.

Problema: weekly/daily consultaban `ops.v_real_trips_business_slice_resolved` en cada request,
recalculando matching + normalized_service_type por fila → CPU 100%, pgsql_tmp lleno, timeouts.

Solución: tablas fact pre-agregadas análogas a `real_business_slice_month_fact`:
  - ops.real_business_slice_day_fact
  - ops.real_business_slice_week_fact

Se pueblan offline (loader incremental), se consultan en < 1s.

Revision ID: 119_business_slice_day_week_facts
Revises: 118_enriched_base_trips_2025_2026
"""

revision = "119_business_slice_day_week_facts"
down_revision = "118_enriched_base_trips_2025_2026"
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.real_business_slice_day_fact (
            trip_date        date NOT NULL,
            country          text,
            city             text,
            business_slice_name text NOT NULL,
            fleet_display_name  text,
            is_subfleet      boolean NOT NULL DEFAULT false,
            subfleet_name    text,
            parent_fleet_name text,
            trips_completed  bigint NOT NULL DEFAULT 0,
            trips_cancelled  bigint NOT NULL DEFAULT 0,
            active_drivers   bigint,
            avg_ticket       numeric,
            commission_pct   numeric,
            trips_per_driver numeric,
            revenue_yego_net numeric,
            cancel_rate_pct  numeric,
            refreshed_at     timestamptz NOT NULL DEFAULT now(),
            loaded_at        timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_bs_day_fact_grain
        ON ops.real_business_slice_day_fact (
            trip_date,
            COALESCE(country, ''),
            COALESCE(city, ''),
            business_slice_name,
            COALESCE(fleet_display_name, ''),
            is_subfleet,
            COALESCE(subfleet_name, ''),
            COALESCE(parent_fleet_name, '')
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_bs_day_fact_date
        ON ops.real_business_slice_day_fact (trip_date)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_bs_day_fact_country_date
        ON ops.real_business_slice_day_fact (country, trip_date)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.real_business_slice_week_fact (
            week_start       date NOT NULL,
            country          text,
            city             text,
            business_slice_name text NOT NULL,
            fleet_display_name  text,
            is_subfleet      boolean NOT NULL DEFAULT false,
            subfleet_name    text,
            parent_fleet_name text,
            trips_completed  bigint NOT NULL DEFAULT 0,
            trips_cancelled  bigint NOT NULL DEFAULT 0,
            active_drivers   bigint,
            avg_ticket       numeric,
            commission_pct   numeric,
            trips_per_driver numeric,
            revenue_yego_net numeric,
            cancel_rate_pct  numeric,
            refreshed_at     timestamptz NOT NULL DEFAULT now(),
            loaded_at        timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_bs_week_fact_grain
        ON ops.real_business_slice_week_fact (
            week_start,
            COALESCE(country, ''),
            COALESCE(city, ''),
            business_slice_name,
            COALESCE(fleet_display_name, ''),
            is_subfleet,
            COALESCE(subfleet_name, ''),
            COALESCE(parent_fleet_name, '')
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_bs_week_fact_ws
        ON ops.real_business_slice_week_fact (week_start)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_bs_week_fact_country_ws
        ON ops.real_business_slice_week_fact (country, week_start)
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ops.real_business_slice_week_fact CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.real_business_slice_day_fact CASCADE")
