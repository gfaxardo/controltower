"""
157 — Yango Loyalty Performance Foundation (Control Foundation Hardening)

Creates serving layer for Yango Loyalty Performance tracking:
- ops.dim_yango_work_rule: Dimension mapping work_rule_id -> city/country
- ops.mv_yango_loyalty_performance_monthly_v1: Materialized view for monthly AD + SH by city

Sources:
- AD: ops.real_business_slice_month_fact (city-resolved, official)
- SH: public.module_ct_fleet_summary_daily via ops.dim_yango_work_rule mapping
- Targets: ops.yango_loyalty_monthly_goals (reused from migration 152)

Additive only. No DROP. No modification to raw tables.

down_revision: 156_ownership_serving_fact_foundation
"""

from alembic import op

revision = "157_yango_loyalty_performance_foundation"
down_revision = "156_ownership_serving_fact_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS ops;")

    # 1. Dimension: work_rule_id -> city/country mapping
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.dim_yango_work_rule (
            work_rule_id TEXT PRIMARY KEY,
            country TEXT NOT NULL DEFAULT 'peru',
            city_norm TEXT NOT NULL,
            label TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dim_yango_work_rule_city
        ON ops.dim_yango_work_rule (country, city_norm);
    """)

    # 2. Seed with known work_rule_ids from discovery
    # These are the 8 work_rule_ids found in module_ct_fleet_summary_daily.
    # City assignment is based on volume analysis against reference values.
    # Can be updated via admin UI or manual UPDATE.
    op.execute("""
        INSERT INTO ops.dim_yango_work_rule (work_rule_id, country, city_norm, label, notes)
        VALUES
            ('8cd100b226b641d8a1592ab718b10980', 'peru', 'lima', 'Lima Principal', 'Largest fleet ~3700 drivers'),
            ('5db2822566574be498f20931784c98f6', 'peru', 'lima', 'Lima Secundario', '~2000 drivers'),
            ('742cd09dc0734a389a2c16394f1616f9', 'peru', 'trujillo', 'Trujillo', '~1200 drivers'),
            ('e26a3cf21acfe01198d50030487e046b', 'peru', 'arequipa', 'Arequipa', '~800 drivers'),
            ('b6192aafcfac436c938e553c656ef5a4', 'peru', 'lima', 'Lima Nuevos', '~500 drivers, low completion'),
            ('1b1528949b624aceb19a3f3525840348', 'peru', 'lima', 'Lima Especial', '~80 drivers'),
            ('656cbf2ed4e7406fa78ec2107ec9fefe', 'peru', 'lima', 'Lima Micro 1', '1 driver'),
            ('f5795e36d67d4d06bf83ec9478fc1b09', 'peru', 'lima', 'Lima Micro 2', '1 driver')
        ON CONFLICT (work_rule_id) DO NOTHING;
    """)

    # 3. Materialized View: Monthly performance by city
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yango_loyalty_performance_monthly_v1 AS
        WITH supply_hours_by_city AS (
            SELECT
                DATE_TRUNC('month', f.fecha)::date AS month_start,
                COALESCE(wr.country, 'peru') AS country,
                COALESCE(wr.city_norm, '_unmapped') AS city_norm,
                COUNT(DISTINCT f.driver_id) FILTER (WHERE f.count_orders_completed > 0) AS active_drivers_sh_source,
                SUM(f.work_time_hours) AS supply_hours_mtd,
                MAX(f.fecha) AS data_until
            FROM public.module_ct_fleet_summary_daily f
            LEFT JOIN ops.dim_yango_work_rule wr ON wr.work_rule_id = f.driver_work_rule_id
            GROUP BY 1, 2, 3
        ),
        active_drivers_by_city AS (
            SELECT
                month AS month_start,
                country,
                city AS city_norm,
                SUM(active_drivers) AS active_drivers_mtd
            FROM ops.real_business_slice_month_fact
            GROUP BY 1, 2, 3
        )
        SELECT
            COALESCE(sh.month_start, ad.month_start) AS month_start,
            COALESCE(sh.country, ad.country) AS country,
            COALESCE(sh.city_norm, ad.city_norm) AS city_norm,
            COALESCE(ad.active_drivers_mtd, sh.active_drivers_sh_source) AS active_drivers_mtd,
            COALESCE(sh.supply_hours_mtd, 0) AS supply_hours_mtd,
            sh.data_until,
            ad.active_drivers_mtd AS ad_official_source,
            sh.active_drivers_sh_source AS ad_fleet_summary_source,
            now() AS refreshed_at
        FROM supply_hours_by_city sh
        FULL OUTER JOIN active_drivers_by_city ad
            ON ad.month_start = sh.month_start
            AND ad.country = sh.country
            AND ad.city_norm = sh.city_norm
        WHERE COALESCE(sh.month_start, ad.month_start) IS NOT NULL;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_yango_loyalty_perf_monthly_v1_pk
        ON ops.mv_yango_loyalty_performance_monthly_v1 (month_start, country, city_norm);
    """)

    # 4. Refresh function
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.refresh_yango_loyalty_performance_monthly_v1(concurrent boolean DEFAULT false)
        RETURNS void AS $$
        BEGIN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_yango_loyalty_performance_monthly_v1;
            ELSE
                REFRESH MATERIALIZED VIEW ops.mv_yango_loyalty_performance_monthly_v1;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_yango_loyalty_performance_monthly_v1(boolean);")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_yango_loyalty_performance_monthly_v1;")
    op.execute("DROP TABLE IF EXISTS ops.dim_yango_work_rule;")
