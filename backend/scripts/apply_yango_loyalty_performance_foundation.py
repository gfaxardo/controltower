#!/usr/bin/env python3
"""
Apply Yango Loyalty Performance Foundation serving layer objects.
Safe: CREATE TABLE IF NOT EXISTS, CREATE MATERIALIZED VIEW IF NOT EXISTS.
No DROP, no UPDATE/DELETE on raw tables.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

init_db_pool()

with get_db() as conn:
    cur = conn.cursor()

    print("=" * 70)
    print("APPLYING: Yango Loyalty Performance Foundation")
    print("=" * 70)

    # 1. Create dimension table
    print("\n[1/4] Creating ops.dim_yango_work_rule...")
    cur.execute("""
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
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_dim_yango_work_rule_city
        ON ops.dim_yango_work_rule (country, city_norm);
    """)
    print("  OK")

    # 2. Seed with known work_rule_ids
    print("\n[2/4] Seeding work_rule -> city mapping...")
    cur.execute("""
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
    cur.execute("SELECT COUNT(*) FROM ops.dim_yango_work_rule")
    count = cur.fetchone()[0]
    print(f"  OK ({count} rows in dim_yango_work_rule)")

    # 3. Create or replace materialized view
    print("\n[3/4] Creating ops.mv_yango_loyalty_performance_monthly_v1...")
    cur.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'ops' AND table_name = 'mv_yango_loyalty_performance_monthly_v1'
    """)
    exists = cur.fetchone()
    if exists:
        print("  MV already exists. Refreshing...")
        cur.execute("REFRESH MATERIALIZED VIEW ops.mv_yango_loyalty_performance_monthly_v1;")
        print("  Refreshed.")
    else:
        cur.execute("""
            CREATE MATERIALIZED VIEW ops.mv_yango_loyalty_performance_monthly_v1 AS
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
        print("  Created.")

    # 4. Create unique index
    print("\n[4/4] Creating unique index...")
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_yango_loyalty_perf_monthly_v1_pk
        ON ops.mv_yango_loyalty_performance_monthly_v1 (month_start, country, city_norm);
    """)
    print("  OK")

    conn.commit()
    print("\n" + "=" * 70)
    print("DONE: Serving layer applied successfully.")
    print("=" * 70)
