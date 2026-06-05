"""
188 — Yango Serving Facts MVs update (OV2-B.3)

Drops and recreates the 5 materialized views over raw_yango with
enhanced fields for serving facts consumption.

Changes from OV2-B.2 (migration 187):
  - mv_orders_day: added api_records, renamed date column, simplified
  - mv_transactions_day: added linked_orders, unlinked_transactions, timestamps
  - mv_revenue_day: aligned field names to OV2-B.3 spec
  - mv_driver_profiles_snapshot: changed to latest-per-driver (non-daily)
  - mv_source_coverage_day: added ingestion_runs_count, updated coverage_status

down_revision: 187_raw_yango_materialized_views
"""

from alembic import op

revision = "188_yango_serving_facts_mvs"
down_revision = "187_raw_yango_materialized_views"
branch_labels = None
depends_on = None


def upgrade():
    # ── mv_orders_day (updated) ──────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_orders_day;")
    op.execute("""
        CREATE MATERIALIZED VIEW raw_yango.mv_orders_day AS
        SELECT
            park_id,
            operational_date AS order_date,
            COUNT(*) AS orders_total,
            COUNT(*) FILTER (WHERE order_status = 'complete') AS orders_completed,
            COUNT(*) FILTER (WHERE order_status = 'cancelled') AS orders_cancelled,
            COUNT(DISTINCT driver_profile_id) AS unique_drivers,
            COUNT(DISTINCT car_id) AS unique_cars,
            MIN(order_created_at) AS first_order_at,
            MAX(order_ended_at) AS last_order_at,
            COUNT(*) AS api_records,
            now() AS refreshed_at
        FROM raw_yango.orders_raw
        GROUP BY park_id, operational_date
        WITH DATA;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_orders_day
        ON raw_yango.mv_orders_day (park_id, order_date);
    """)


    # ── mv_transactions_day (updated) ─────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_transactions_day;")
    op.execute("""
        CREATE MATERIALIZED VIEW raw_yango.mv_transactions_day AS
        SELECT
            park_id,
            operational_date AS transaction_date,
            COALESCE(currency_code, 'PEN') AS currency,
            category_name AS transaction_category,
            COUNT(*) AS transactions_count,
            COALESCE(SUM(amount), 0) AS amount_sum,
            COALESCE(SUM(ABS(amount)), 0) AS amount_abs_sum,
            COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0) AS positive_amount_sum,
            COALESCE(SUM(amount) FILTER (WHERE amount < 0), 0) AS negative_amount_sum,
            COUNT(DISTINCT driver_profile_id) AS unique_drivers,
            COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != '') AS linked_orders,
            COUNT(*) FILTER (WHERE order_id IS NULL OR order_id = '') AS unlinked_transactions,
            MIN(event_at) AS first_transaction_at,
            MAX(event_at) AS last_transaction_at,
            now() AS refreshed_at
        FROM raw_yango.transactions_raw
        GROUP BY park_id, operational_date, COALESCE(currency_code, 'PEN'), category_name
        WITH DATA;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_transactions_day
        ON raw_yango.mv_transactions_day (park_id, transaction_date, transaction_category, currency);
    """)


    # ── mv_revenue_day (updated) ──────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_revenue_day;")
    op.execute("""
        CREATE MATERIALIZED VIEW raw_yango.mv_revenue_day AS
        SELECT
            park_id,
            operational_date AS revenue_date,
            COALESCE(currency_code, 'PEN') AS currency,
            COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0) AS partner_fee_trip_amount,
            COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS partner_fee_trip_count,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Service fee for trip'), 0) AS service_fee_trip_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Service fee, VAT'), 0) AS service_fee_vat_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name IN ('Cash', 'Card payment')), 0) AS gmv_cash_card_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Promo code compensation'), 0) AS promo_compensation_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name NOT IN (
                'Partner fee for trip', 'Cash', 'Card payment',
                'Service fee for trip', 'Service fee, VAT', 'Promo code compensation'
            )), 0) AS adjustments_amount,
            COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0) AS revenue_candidate_amount,
            COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS revenue_candidate_count,
            COUNT(DISTINCT order_id) FILTER (WHERE category_name = 'Partner fee for trip' AND order_id IS NOT NULL AND order_id != '') AS linked_orders,
            CASE WHEN COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != '') > 0
                 THEN COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0)
                      / NULLIF(COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != ''), 0)
                 ELSE 0
            END AS revenue_per_order,
            CASE WHEN COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') > 0
                 THEN COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0)
                      / NULLIF(COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip'), 0)
                 ELSE 0
            END AS revenue_per_partner_fee_txn,
            now() AS refreshed_at
        FROM raw_yango.transactions_raw
        GROUP BY park_id, operational_date, COALESCE(currency_code, 'PEN')
        WITH DATA;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_revenue_day
        ON raw_yango.mv_revenue_day (park_id, revenue_date, currency);
    """)


    # ── mv_driver_profiles_snapshot (updated to per-driver) ───
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_driver_profiles_snapshot;")
    op.execute("""
        CREATE MATERIALIZED VIEW raw_yango.mv_driver_profiles_snapshot AS
        SELECT DISTINCT ON (park_id, driver_profile_id)
            park_id,
            driver_profile_id,
            MAX(api_fetched_at) AS last_seen_at,
            (ARRAY_AGG(raw_payload_hash ORDER BY api_fetched_at DESC))[1] AS latest_payload_hash,
            (ARRAY_AGG(work_status ORDER BY api_fetched_at DESC))[1] AS raw_status,
            (ARRAY_AGG(car_id ORDER BY api_fetched_at DESC))[1] AS car_id,
            now() AS refreshed_at
        FROM raw_yango.driver_profiles_raw
        WHERE driver_profile_id IS NOT NULL AND driver_profile_id != ''
        GROUP BY park_id, driver_profile_id
        WITH DATA;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_driver_profiles_snapshot
        ON raw_yango.mv_driver_profiles_snapshot (park_id, driver_profile_id);
    """)


    # ── mv_source_coverage_day (updated) ──────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_source_coverage_day;")
    op.execute("""
        CREATE MATERIALIZED VIEW raw_yango.mv_source_coverage_day AS
        WITH
        orders_daily AS (
            SELECT park_id, operational_date, COUNT(*) AS orders_count
            FROM raw_yango.orders_raw GROUP BY park_id, operational_date
        ),
        txns_daily AS (
            SELECT park_id, operational_date,
                   COUNT(*) AS transactions_count,
                   COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS revenue_candidate_count
            FROM raw_yango.transactions_raw GROUP BY park_id, operational_date
        ),
        runs_daily AS (
            SELECT park_id, date_from AS operational_date, COUNT(*) AS ingestion_runs_count
            FROM raw_yango.api_ingestion_run
            WHERE status = 'completed'
            GROUP BY park_id, date_from
        ),
        all_dates AS (
            SELECT park_id, operational_date FROM orders_daily UNION
            SELECT park_id, operational_date FROM txns_daily
        )
        SELECT
            d.park_id,
            d.operational_date AS coverage_date,
            COALESCE(o.orders_count, 0) > 0 AS has_orders,
            COALESCE(t.transactions_count, 0) > 0 AS has_transactions,
            COALESCE(t.revenue_candidate_count, 0) > 0 AS has_revenue_candidate,
            COALESCE(o.orders_count, 0) AS orders_count,
            COALESCE(t.transactions_count, 0) AS transactions_count,
            COALESCE(t.revenue_candidate_count, 0) AS revenue_candidate_count,
            (SELECT MIN(api_fetched_at) FROM raw_yango.orders_raw WHERE park_id = d.park_id) AS first_api_fetched_at,
            (SELECT MAX(api_fetched_at) FROM raw_yango.transactions_raw WHERE park_id = d.park_id) AS last_api_fetched_at,
            COALESCE(r.ingestion_runs_count, 0) AS ingestion_runs_count,
            CASE
                WHEN COALESCE(o.orders_count, 0) > 0
                 AND COALESCE(t.transactions_count, 0) > 0
                 AND COALESCE(t.revenue_candidate_count, 0) > 0 THEN 'FULL'
                WHEN COALESCE(o.orders_count, 0) > 0
                 AND COALESCE(t.transactions_count, 0) = 0 THEN 'ORDERS_ONLY'
                WHEN COALESCE(o.orders_count, 0) = 0
                 AND COALESCE(t.transactions_count, 0) > 0 THEN 'TRANSACTIONS_ONLY'
                WHEN COALESCE(o.orders_count, 0) > 0
                  OR COALESCE(t.transactions_count, 0) > 0 THEN 'PARTIAL'
                ELSE 'MISSING'
            END AS coverage_status,
            now() AS refreshed_at
        FROM all_dates d
        LEFT JOIN orders_daily o ON d.park_id = o.park_id AND d.operational_date = o.operational_date
        LEFT JOIN txns_daily t ON d.park_id = t.park_id AND d.operational_date = t.operational_date
        LEFT JOIN runs_daily r ON d.park_id = r.park_id AND d.operational_date = r.operational_date
        WITH DATA;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_source_coverage_day
        ON raw_yango.mv_source_coverage_day (park_id, coverage_date);
    """)


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_source_coverage_day;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_driver_profiles_snapshot;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_revenue_day;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_transactions_day;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_orders_day;")
