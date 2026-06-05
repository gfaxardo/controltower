"""
187 — Raw Yango Materialized Views (OV2-B.2)

Creates 5 materialized views over raw_yango:
- mv_orders_day
- mv_transactions_day
- mv_revenue_day
- mv_driver_profiles_snapshot
- mv_source_coverage_day

All MVs support REFRESH CONCURRENTLY via UNIQUE indexes.

down_revision: 186_raw_yango_operational_date
"""

from alembic import op

revision = "187_raw_yango_materialized_views"
down_revision = "186_raw_yango_operational_date"
branch_labels = None
depends_on = None


def upgrade():
    # ── mv_orders_day ──────────────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS raw_yango.mv_orders_day AS
        SELECT
            park_id,
            operational_date,
            COUNT(*) AS orders_total,
            COUNT(*) FILTER (WHERE order_status = 'complete') AS orders_finished,
            COUNT(*) FILTER (WHERE order_status = 'cancelled') AS orders_cancelled,
            COUNT(*) FILTER (WHERE order_status NOT IN ('complete', 'cancelled')) AS orders_other_status,
            COUNT(DISTINCT driver_profile_id) AS unique_drivers_with_orders,
            COUNT(DISTINCT car_id) AS unique_cars_with_orders,
            COUNT(DISTINCT category) AS unique_categories,
            SUM(mileage) AS total_mileage,
            MIN(order_created_at) AS first_order_at,
            MAX(order_ended_at) AS last_order_at,
            AVG(price) AS avg_price,
            COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price), 0) AS median_price,
            SUM(price) AS gmv_sum,
            now() AS refreshed_at
        FROM raw_yango.orders_raw
        GROUP BY park_id, operational_date
        WITH DATA;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_orders_day
        ON raw_yango.mv_orders_day (park_id, operational_date);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_orders_day_date
        ON raw_yango.mv_orders_day (operational_date);
    """)

    # ── mv_transactions_day ────────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS raw_yango.mv_transactions_day AS
        SELECT
            park_id,
            operational_date,
            category_name,
            COALESCE(currency_code, 'PEN') AS currency_code,
            COUNT(*) AS transaction_count,
            COALESCE(SUM(amount), 0) AS amount_sum,
            COALESCE(SUM(ABS(amount)), 0) AS amount_abs_sum,
            COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0) AS positive_amount_sum,
            COALESCE(SUM(amount) FILTER (WHERE amount < 0), 0) AS negative_amount_sum,
            COUNT(DISTINCT driver_profile_id) AS unique_drivers,
            COUNT(DISTINCT order_id) AS unique_orders,
            now() AS refreshed_at
        FROM raw_yango.transactions_raw
        GROUP BY park_id, operational_date, category_name, COALESCE(currency_code, 'PEN')
        WITH DATA;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_transactions_day
        ON raw_yango.mv_transactions_day (park_id, operational_date, category_name, currency_code);
    """)

    # ── mv_revenue_day ─────────────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS raw_yango.mv_revenue_day AS
        SELECT
            park_id,
            operational_date,
            COALESCE(currency_code, 'PEN') AS currency_code,
            COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0) AS revenue_yego_partner_fee,
            COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS revenue_yego_partner_fee_count,
            COALESCE(SUM(amount) FILTER (WHERE category_name IN ('Cash', 'Card payment')), 0) AS gmv_cash_card,
            COUNT(*) FILTER (WHERE category_name IN ('Cash', 'Card payment')) AS gmv_cash_card_count,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Service fee for trip'), 0) AS platform_fee,
            COUNT(*) FILTER (WHERE category_name = 'Service fee for trip') AS platform_fee_count,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Service fee, VAT'), 0) AS platform_fee_vat,
            COUNT(*) FILTER (WHERE category_name = 'Service fee, VAT') AS platform_fee_vat_count,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Promo code compensation'), 0) AS promo_compensation,
            COUNT(*) FILTER (WHERE category_name = 'Promo code compensation') AS promo_compensation_count,
            COALESCE(SUM(amount) FILTER (WHERE category_name NOT IN (
                'Partner fee for trip', 'Cash', 'Card payment',
                'Service fee for trip', 'Service fee, VAT', 'Promo code compensation'
            )), 0) AS other_adjustments,
            COUNT(*) FILTER (WHERE category_name NOT IN (
                'Partner fee for trip', 'Cash', 'Card payment',
                'Service fee for trip', 'Service fee, VAT', 'Promo code compensation'
            )) AS other_adjustments_count,
            COUNT(*) AS total_txn_count,
            CASE WHEN COUNT(DISTINCT order_id) > 0
                 THEN COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0)
                      / NULLIF(COUNT(DISTINCT order_id), 0)
                 ELSE 0
            END AS revenue_per_order,
            now() AS refreshed_at
        FROM raw_yango.transactions_raw
        GROUP BY park_id, operational_date, COALESCE(currency_code, 'PEN')
        WITH DATA;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_revenue_day
        ON raw_yango.mv_revenue_day (park_id, operational_date, currency_code);
    """)

    # ── mv_driver_profiles_snapshot ────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS raw_yango.mv_driver_profiles_snapshot AS
        SELECT DISTINCT ON (park_id, driver_profile_id, operational_date)
            park_id,
            driver_profile_id,
            operational_date AS snapshot_date,
            work_status,
            car_id,
            car_category,
            has_contract_issue,
            raw_payload_hash,
            api_fetched_at,
            now() AS refreshed_at
        FROM raw_yango.driver_profiles_raw
        WHERE driver_profile_id IS NOT NULL AND driver_profile_id != ''
        ORDER BY park_id, driver_profile_id, operational_date, api_fetched_at DESC
        WITH DATA;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_driver_profiles_snapshot
        ON raw_yango.mv_driver_profiles_snapshot (park_id, driver_profile_id, snapshot_date);
    """)

    # ── mv_source_coverage_day ─────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS raw_yango.mv_source_coverage_day AS
        WITH
        orders_daily AS (
            SELECT park_id, operational_date, COUNT(*) AS orders_count
            FROM raw_yango.orders_raw
            GROUP BY park_id, operational_date
        ),
        txns_daily AS (
            SELECT park_id, operational_date,
                   COUNT(*) AS transactions_count,
                   COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS revenue_candidate_count,
                   COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0) AS revenue_candidate_amount
            FROM raw_yango.transactions_raw
            GROUP BY park_id, operational_date
        ),
        drivers_daily AS (
            SELECT park_id, operational_date, COUNT(*) AS driver_profiles_count
            FROM raw_yango.driver_profiles_raw
            GROUP BY park_id, operational_date
        ),
        all_dates AS (
            SELECT park_id, operational_date FROM orders_daily
            UNION
            SELECT park_id, operational_date FROM txns_daily
            UNION
            SELECT park_id, operational_date FROM drivers_daily
        )
        SELECT
            d.park_id,
            d.operational_date,
            COALESCE(o.orders_count, 0) > 0 AS has_orders,
            COALESCE(t.transactions_count, 0) > 0 AS has_transactions,
            COALESCE(dp.driver_profiles_count, 0) > 0 AS has_driver_profiles,
            COALESCE(o.orders_count, 0) AS orders_count,
            COALESCE(t.transactions_count, 0) AS transactions_count,
            COALESCE(dp.driver_profiles_count, 0) AS driver_profiles_count,
            COALESCE(t.revenue_candidate_count, 0) AS revenue_candidate_count,
            COALESCE(t.revenue_candidate_amount, 0) AS revenue_candidate_amount,
            CASE
                WHEN COALESCE(o.orders_count, 0) > 0
                 AND COALESCE(t.transactions_count, 0) > 0
                 AND COALESCE(dp.driver_profiles_count, 0) > 0 THEN 'full'
                WHEN COALESCE(o.orders_count, 0) > 0
                  OR COALESCE(t.transactions_count, 0) > 0
                  OR COALESCE(dp.driver_profiles_count, 0) > 0 THEN 'partial'
                ELSE 'empty'
            END AS coverage_status,
            now() AS refreshed_at
        FROM all_dates d
        LEFT JOIN orders_daily o ON d.park_id = o.park_id AND d.operational_date = o.operational_date
        LEFT JOIN txns_daily t ON d.park_id = t.park_id AND d.operational_date = t.operational_date
        LEFT JOIN drivers_daily dp ON d.park_id = dp.park_id AND d.operational_date = dp.operational_date
        WITH DATA;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_source_coverage_day
        ON raw_yango.mv_source_coverage_day (park_id, operational_date);
    """)


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_source_coverage_day;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_driver_profiles_snapshot;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_revenue_day;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_transactions_day;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_orders_day;")
