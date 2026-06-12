"""
211 — CF-H2F.1: Business Slice Mapping Foundation

Creates:
- dim.yango_category_to_slice

Maps Yango order categories to CT business_slice_name.
Shadow mode only — does NOT modify production Omniview serving facts.

down_revision: 210_cf_h2g_omniview_canonical_source_mapper
"""

from alembic import op

revision = "211_cf_h2f1_business_slice_mapping"
down_revision = "210_cf_h2g_omniview_canonical_source_mapper"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS dim;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS dim.yango_category_to_slice (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            park_id             text NOT NULL DEFAULT '08e20910d81d42658d4334d3f6d10ac0',
            yango_category      text NOT NULL,
            business_slice_name text NOT NULL,
            fleet_display_name  text,
            confidence          text NOT NULL DEFAULT 'MEDIUM',
            mapping_status      text NOT NULL DEFAULT 'MAPPED',
            evidence_count      integer DEFAULT 0,
            first_seen_at       timestamptz,
            last_seen_at        timestamptz,
            notes               text,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now(),

            UNIQUE (park_id, yango_category)
        );
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_yango_cat_slice_park "
        "ON dim.yango_category_to_slice (park_id, yango_category);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_yango_cat_slice_name "
        "ON dim.yango_category_to_slice (business_slice_name);"
    )

    op.execute("""
        INSERT INTO dim.yango_category_to_slice
            (park_id, yango_category, business_slice_name, fleet_display_name,
             confidence, mapping_status, notes)
        VALUES
        ('08e20910d81d42658d4334d3f6d10ac0', 'econom',       'Auto regular', 'Econom (Auto)',        'HIGH',   'MAPPED', 'Primary category. 83.6% of orders.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'comfort',      'Auto regular', 'Comfort (Auto)',        'HIGH',   'MAPPED', 'Premium auto. Same service class as econom.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'comfort_plus', 'Auto regular', 'Comfort+ (Auto)',        'HIGH',   'MAPPED', 'Top-tier auto. Same service class as econom/comfort.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'business',     'PRO',          'Business (PRO)',         'MEDIUM', 'MAPPED', 'Business class. Maps to PRO slice. Avg price 21.39 vs econom 14.27.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'minivan',      'YMA',          'Minivan (YMA)',          'MEDIUM', 'MAPPED', 'Large vehicle. Maps to YMA slice. Could be Auto regular but price/class differ.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'express',      'Delivery',     'Express (Delivery)',     'HIGH',   'MAPPED', 'Express delivery service.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'tuktuk',       'Tuk Tuk',      'Tuk Tuk',               'HIGH',   'MAPPED', 'Mototaxi service. Avg price 3.58 confirms Tuk Tuk.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'cargo',        'Carga',        'Cargo',                  'HIGH',   'MAPPED', 'Cargo/freight service. Avg price 47.00 confirms.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'courier',      'Delivery',     'Courier (Delivery)',     'HIGH',   'MAPPED', 'Courier delivery. Only 3 orders.'),
        ('08e20910d81d42658d4334d3f6d10ac0', 'summit_b2b',   'Auto regular', 'Summit B2B (Auto)',      'MEDIUM', 'MAPPED', 'B2B taxi service. Only 10 orders. Avg price 25.28.')
        ON CONFLICT (park_id, yango_category) DO NOTHING;
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS dim.yango_category_to_slice CASCADE;")
