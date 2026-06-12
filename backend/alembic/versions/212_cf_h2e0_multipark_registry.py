"""
212 — CF-H2E.0: Multipark Registry Foundation

Creates:
- ops.yango_park_registry

Populates 6 parks from api_keys_yego.xlsx.
Shadow mode only — does NOT activate multipark ingestion.

down_revision: 211_cf_h2f1_business_slice_mapping
"""

from alembic import op

revision = "212_cf_h2e0_multipark_registry"
down_revision = "211_cf_h2f1_business_slice_mapping"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_park_registry (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            park_id             text NOT NULL UNIQUE,
            park_name           text NOT NULL,
            fleet_name          text,
            country             text NOT NULL DEFAULT 'peru',
            city                text,
            timezone            text DEFAULT 'America/Lima',
            currency            text DEFAULT 'PEN',
            line_of_business    text DEFAULT 'autos regular',
            api_key_present     boolean NOT NULL DEFAULT false,
            credential_status   text NOT NULL DEFAULT 'NOT_REGISTERED',
            shadow_enabled      boolean NOT NULL DEFAULT false,
            shadow_priority     integer DEFAULT 0,
            park_tier           text NOT NULL DEFAULT 'TIER_3',
            ingestion_active    boolean NOT NULL DEFAULT false,
            total_orders_ingested integer DEFAULT 0,
            first_ingested_at   timestamptz,
            last_ingested_at    timestamptz,
            active              boolean NOT NULL DEFAULT true,
            notes               text,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now()
        );
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_yango_park_registry_active "
        "ON ops.yango_park_registry (active, shadow_priority);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_yango_park_registry_tier "
        "ON ops.yango_park_registry (park_tier, country, city);"
    )

    op.execute("""
        INSERT INTO ops.yango_park_registry
            (park_id, park_name, fleet_name, country, city, timezone, currency,
             line_of_business, api_key_present, credential_status,
             shadow_enabled, shadow_priority, park_tier,
             ingestion_active, total_orders_ingested, notes)
        VALUES
        ('08e20910d81d42658d4334d3f6d10ac0', 'Yego Lima',    'YEGO Lima',    'peru', 'lima',      'America/Lima', 'PEN', 'autos regular', true, 'REGISTERED',
         true,  10, 'TIER_1', true,  44389, 'Production baseline. Only park with ingested data. CF-H2C/D certified.'),
        ('851e30755bba4d298e2e837f571b4ab8', 'Yego Trujillo', 'YEGO Trujillo', 'peru', 'trujillo',   'America/Lima', 'PEN', 'autos regular', true, 'CREDENTIALS_READY',
         false, 20, 'TIER_2', false, 0,     'Credentials verified. dim_park confirmed. Ready for shadow pilot.'),
        ('56e4607dfc354e0a9cde4f0aa7973003', 'Yego Arequipa', 'YEGO Arequipa', 'peru', 'arequipa',   'America/Lima', 'PEN', 'autos regular', true, 'CREDENTIALS_READY',
         false, 30, 'TIER_2', false, 0,     'Credentials verified. dim_park confirmed. Ready for shadow pilot.'),
        ('64085dd85e124e2c808806f70d527ea8', 'Yego Pro',      'YEGO Pro',      'peru', 'lima',      'America/Lima', 'PEN', 'autos regular', true, 'CREDENTIALS_READY',
         false, 40, 'TIER_2', false, 0,     'Premium fleet (Lima). Tests multi-fleet same-city ingestion.'),
        ('e3e07c00ed914f82a59c03283a178d6e', 'Yego TukTuk',   'YEGO TukTuk',   'peru', 'lima',      'America/Lima', 'PEN', 'autos regular', true, 'CREDENTIALS_READY',
         false, 50, 'TIER_3', false, 0,     'TukTuk fleet (Lima). Different vehicle category. Low volume expected.'),
        ('fafd623109d740f8a1f15af7c3dd86c6', 'Yego Mi Auto',  'YEGO Mi Auto',  'peru', 'unknown',   'America/Lima', 'PEN', 'autos regular', true, 'METADATA_INCOMPLETE',
         false, 60, 'TIER_3', false, 0,     'NOT in dim_park. City unknown. Blocked until metadata resolved.')
        ON CONFLICT (park_id) DO NOTHING;
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ops.yango_park_registry CASCADE;")
