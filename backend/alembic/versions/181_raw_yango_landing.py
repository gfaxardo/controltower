"""
181 — Raw Yango Landing (OV2-B.0)

Creates:
- raw_yango schema
- raw_yango.api_park_credentials_registry
- raw_yango.api_ingestion_run
- raw_yango.orders_raw
- raw_yango.transactions_raw
- raw_yango.driver_profiles_raw
- raw_yango.ingestion_errors

Additive. No DROP on existing tables.
Reglas:
- API keys NEVER stored in DB (env_var_name only).
- Deduplication via UNIQUE(park_id, business_id, raw_payload_hash).
- ON CONFLICT DO NOTHING for unchanged payloads.
- Downgrade: DROP tables in reverse dependency order, then DROP SCHEMA.

down_revision: 180_yego_lima_capacity_config
"""

from alembic import op

revision = "181_raw_yango_landing"
down_revision = "180_yego_lima_capacity_config"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS raw_yango;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_yango.api_park_credentials_registry (
            id            SERIAL PRIMARY KEY,
            credential_id TEXT NOT NULL UNIQUE,
            park_id       TEXT NOT NULL,
            country       TEXT,
            city          TEXT,
            fleet_name    TEXT,
            env_var_name  TEXT NOT NULL,
            api_base_url  TEXT NOT NULL,
            is_active     BOOLEAN NOT NULL DEFAULT true,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            notes         TEXT
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_yango.api_ingestion_run (
            id                SERIAL PRIMARY KEY,
            run_id            TEXT NOT NULL UNIQUE,
            endpoint_group    TEXT NOT NULL,
            park_id           TEXT NOT NULL,
            date_from         DATE NOT NULL,
            date_to           DATE NOT NULL,
            status            TEXT NOT NULL DEFAULT 'running',
            started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at       TIMESTAMPTZ,
            records_fetched   INTEGER DEFAULT 0,
            records_inserted  INTEGER DEFAULT 0,
            records_updated   INTEGER DEFAULT 0,
            record_skips      INTEGER DEFAULT 0,
            error_count       INTEGER DEFAULT 0,
            warning_count     INTEGER DEFAULT 0,
            max_concurrency   INTEGER DEFAULT 3,
            source            TEXT DEFAULT 'yango_fleet_api',
            script_version    TEXT,
            notes             TEXT
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_run_park_date
        ON raw_yango.api_ingestion_run (park_id, date_from);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_yango.orders_raw (
            id                SERIAL PRIMARY KEY,
            park_id           TEXT NOT NULL,
            order_id          TEXT NOT NULL,
            order_short_id    INTEGER,
            order_status      TEXT,
            order_created_at  TIMESTAMPTZ,
            order_booked_at   TIMESTAMPTZ,
            order_ended_at    TIMESTAMPTZ,
            driver_profile_id TEXT,
            car_id            TEXT,
            category          TEXT,
            payment_method    TEXT,
            provider          TEXT,
            price             NUMERIC,
            mileage           NUMERIC,
            currency_code     TEXT DEFAULT 'PEN',
            raw_payload       JSONB NOT NULL,
            raw_payload_hash  TEXT NOT NULL,
            api_fetched_at    TIMESTAMPTZ NOT NULL,
            api_run_id        TEXT,
            source_endpoint   TEXT,
            schema_version    TEXT,
            inserted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        ALTER TABLE raw_yango.orders_raw
        ADD CONSTRAINT uq_yango_orders_raw
        UNIQUE (park_id, order_id, raw_payload_hash);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_orders_park_date
        ON raw_yango.orders_raw (park_id, api_fetched_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_orders_driver
        ON raw_yango.orders_raw (driver_profile_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_orders_run
        ON raw_yango.orders_raw (api_run_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_yango.transactions_raw (
            id                   SERIAL PRIMARY KEY,
            park_id              TEXT NOT NULL,
            transaction_id       TEXT NOT NULL,
            event_at             TIMESTAMPTZ,
            category_id          TEXT,
            category_name        TEXT,
            group_id             TEXT,
            amount               NUMERIC,
            currency_code        TEXT DEFAULT 'PEN',
            description          TEXT,
            driver_profile_id    TEXT,
            order_id             TEXT,
            created_by_identity  TEXT,
            raw_payload          JSONB NOT NULL,
            raw_payload_hash     TEXT NOT NULL,
            api_fetched_at       TIMESTAMPTZ NOT NULL,
            api_run_id           TEXT,
            source_endpoint      TEXT,
            schema_version       TEXT,
            inserted_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        ALTER TABLE raw_yango.transactions_raw
        ADD CONSTRAINT uq_yango_txn_raw
        UNIQUE (park_id, transaction_id, raw_payload_hash);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_txn_park_date
        ON raw_yango.transactions_raw (park_id, api_fetched_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_txn_category
        ON raw_yango.transactions_raw (category_name);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_txn_group
        ON raw_yango.transactions_raw (group_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_txn_order
        ON raw_yango.transactions_raw (order_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_txn_driver
        ON raw_yango.transactions_raw (driver_profile_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_txn_run
        ON raw_yango.transactions_raw (api_run_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_yango.driver_profiles_raw (
            id                  SERIAL PRIMARY KEY,
            park_id             TEXT NOT NULL,
            driver_profile_id   TEXT NOT NULL,
            work_status         TEXT,
            car_id              TEXT,
            car_category        TEXT,
            has_contract_issue  BOOLEAN,
            raw_payload         JSONB NOT NULL,
            raw_payload_hash    TEXT NOT NULL,
            api_fetched_at      TIMESTAMPTZ NOT NULL,
            api_run_id          TEXT,
            source_endpoint     TEXT,
            schema_version      TEXT,
            inserted_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        ALTER TABLE raw_yango.driver_profiles_raw
        ADD CONSTRAINT uq_yango_drivers_raw
        UNIQUE (park_id, driver_profile_id, raw_payload_hash);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_drivers_park
        ON raw_yango.driver_profiles_raw (park_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_drivers_work_status
        ON raw_yango.driver_profiles_raw (work_status);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_yango.ingestion_errors (
            id                       SERIAL PRIMARY KEY,
            run_id                   TEXT,
            park_id                  TEXT NOT NULL,
            endpoint_group           TEXT,
            endpoint_url_sanitized   TEXT,
            request_params_json      JSONB,
            status_code              INTEGER,
            error_type               TEXT,
            error_message_sanitized  TEXT,
            retry_count              INTEGER DEFAULT 0,
            occurred_at              TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_errors_run
        ON raw_yango.ingestion_errors (run_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS raw_yango.ingestion_errors;")
    op.execute("DROP TABLE IF EXISTS raw_yango.driver_profiles_raw;")
    op.execute("DROP TABLE IF EXISTS raw_yango.transactions_raw;")
    op.execute("DROP TABLE IF EXISTS raw_yango.orders_raw;")
    op.execute("DROP TABLE IF EXISTS raw_yango.api_ingestion_run;")
    op.execute("DROP TABLE IF EXISTS raw_yango.api_park_credentials_registry;")
    op.execute("DROP SCHEMA IF EXISTS raw_yango;")
