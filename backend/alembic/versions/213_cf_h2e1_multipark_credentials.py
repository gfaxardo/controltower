"""
213 — CF-H2E.1: Multipark Credential Registry Population

Adds 5 pilot parks to raw_yango.api_park_credentials_registry.
Credentials resolved from environment variables.
Shadow mode only — does NOT activate production ingestion.

down_revision: 212_cf_h2e0_multipark_registry
"""

from alembic import op

revision = "213_cf_h2e1_multipark_credentials"
down_revision = "212_cf_h2e0_multipark_registry"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE raw_yango.api_park_credentials_registry
        ADD COLUMN IF NOT EXISTS credential_status text DEFAULT 'REGISTERED',
        ADD COLUMN IF NOT EXISTS last_validation_at timestamptz,
        ADD COLUMN IF NOT EXISTS park_name text;
    """)

    op.execute("""
        UPDATE raw_yango.api_park_credentials_registry
        SET credential_status = 'REGISTERED',
            park_name = 'Yego Lima'
        WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
          AND credential_status IS NULL;
    """)

    parks_data = [
        ("08e20910d81d42658d4334d3f6d10ac0", "yego_lima_01", "YEGO Lima",    "Yego Lima",    "Peru", "Lima",      "YANGO_LIMA",     "REGISTERED"),
        ("851e30755bba4d298e2e837f571b4ab8", "yego_trujillo_01", "YEGO Trujillo", "Yego Trujillo", "Peru", "Trujillo",   "YANGO_TRUJILLO",  "CREDENTIALS_READY"),
        ("56e4607dfc354e0a9cde4f0aa7973003", "yego_arequipa_01", "YEGO Arequipa", "Yego Arequipa", "Peru", "Arequipa",   "YANGO_AREQUIPA",  "CREDENTIALS_READY"),
        ("64085dd85e124e2c808806f70d527ea8", "yego_pro_01", "YEGO Pro",      "Yego Pro",      "Peru", "Lima",      "YANGO_PRO",       "CREDENTIALS_READY"),
        ("e3e07c00ed914f82a59c03283a178d6e", "yego_tuktuk_01", "YEGO TukTuk",   "Yego TukTuk",   "Peru", "Lima",      "YANGO_TUKTUK",    "CREDENTIALS_READY"),
    ]
    for pid, cred_id, fleet, pname, country, city, env, status in parks_data:
        op.execute(f"""
            INSERT INTO raw_yango.api_park_credentials_registry
                (credential_id, park_id, fleet_name, park_name, country, city, env_var_name,
                 api_base_url, is_active, credential_status)
            SELECT '{cred_id}', '{pid}', '{fleet}', '{pname}', '{country}', '{city}', '{env}',
                   'https://fleet-api.yango.tech', true, '{status}'
            WHERE NOT EXISTS (
                SELECT 1 FROM raw_yango.api_park_credentials_registry
                WHERE park_id = '{pid}'
            );
        """)


def downgrade():
    op.execute("""
        DELETE FROM raw_yango.api_park_credentials_registry
        WHERE park_id IN (
            '851e30755bba4d298e2e837f571b4ab8',
            '56e4607dfc354e0a9cde4f0aa7973003',
            '64085dd85e124e2c808806f70d527ea8',
            'e3e07c00ed914f82a59c03283a178d6e'
        );
    """)
