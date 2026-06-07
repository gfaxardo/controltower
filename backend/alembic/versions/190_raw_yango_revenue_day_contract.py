"""
190 — Revenue MV canonical contract (OV2-B.7)

Drops and recreates mv_revenue_day with OV2 canonical column names
and additional governance fields.

Changes from OV2-B.3 (migration 188):
  - partner_fee_trip_amount → revenue_partner_fee_amount
  - partner_fee_trip_count → revenue_partner_fee_count
  - service_fee_trip_amount → platform_fee_amount
  - service_fee_vat_amount → platform_fee_vat_amount
  - gmv_cash_card_amount split into gmv_cash_amount + gmv_card_amount
  - promo_compensation_amount (unchanged)
  - adjustments_amount (unchanged)
  - ADDED: refunds_amount (from Reimbursement for user cancellations)
  - ADDED: total_transactions_count
  - ADDED: revenue_source = 'YANGO_TRANSACTIONS_API'
  - ADDED: revenue_confidence = 'AUDIT_CERTIFIED'

No serving productivo touched. Shadow mode only.
canonical_ready remains false at API level.

down_revision: 189_ingestion_reliability_hardening
"""

from alembic import op

revision = "190_raw_yango_revenue_day_contract"
down_revision = "189_ingestion_reliability_hardening"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_revenue_day;")
    op.execute("""
        CREATE MATERIALIZED VIEW raw_yango.mv_revenue_day AS
        SELECT
            park_id,
            operational_date AS revenue_date,
            COALESCE(currency_code, 'PEN') AS currency,
            COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0) AS revenue_partner_fee_amount,
            COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS revenue_partner_fee_count,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Service fee for trip'), 0) AS platform_fee_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Service fee, VAT'), 0) AS platform_fee_vat_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Cash'), 0) AS gmv_cash_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Card payment'), 0) AS gmv_card_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Promo code discount compensation'), 0) AS promo_compensation_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name NOT IN (
                'Partner fee for trip', 'Cash', 'Card payment',
                'Service fee for trip', 'Service fee, VAT',
                'Promo code discount compensation',
                'Reimbursement for user cancellations'
            )), 0) AS adjustments_amount,
            COALESCE(SUM(amount) FILTER (WHERE category_name = 'Reimbursement for user cancellations'), 0) AS refunds_amount,
            COUNT(*) AS total_transactions_count,
            COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != '') AS linked_orders,
            CASE WHEN COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != '') > 0
                 THEN COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0)
                      / NULLIF(COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != ''), 0)
                 ELSE NULL
            END AS revenue_per_order,
            CASE WHEN COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') > 0
                 THEN COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0)
                      / NULLIF(COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip'), 0)
                 ELSE NULL
            END AS revenue_per_partner_fee_txn,
            'YANGO_TRANSACTIONS_API' AS revenue_source,
            'AUDIT_CERTIFIED' AS revenue_confidence,
            now() AS refreshed_at
        FROM raw_yango.transactions_raw
        GROUP BY park_id, operational_date, COALESCE(currency_code, 'PEN')
        WITH DATA;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_revenue_day
        ON raw_yango.mv_revenue_day (park_id, revenue_date, currency);
    """)


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS raw_yango.mv_revenue_day;")
    # Recreate the previous version from migration 188
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
        WITH NO DATA;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_revenue_day
        ON raw_yango.mv_revenue_day (park_id, revenue_date, currency);
    """)
