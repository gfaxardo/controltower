"""
138 — Plan versions metadata: governance de versiones de proyección.

Agrega tabla plan.plan_versions_metadata para almacenar display_name,
description, source_filename y metadatos operativos por versión.

El plan_version_key técnico NO se modifica en tablas existentes.
El rename solo afecta display_name en esta tabla de metadata.

down_revision: 137_plan_vs_real_monthly_materialized_facts
"""

from alembic import op

revision = "138_plan_versions_metadata"
down_revision = "137_plan_vs_real_monthly_materialized_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS plan")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS plan.plan_versions_metadata (
            id                  BIGSERIAL PRIMARY KEY,
            plan_version_key    TEXT NOT NULL UNIQUE,
            display_name        TEXT NOT NULL,
            description         TEXT,
            source_filename     TEXT,
            uploaded_by         TEXT,
            uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status              TEXT NOT NULL DEFAULT 'active',
            row_count           INTEGER,
            valid_rows          INTEGER,
            invalid_rows        INTEGER,
            min_period          DATE,
            max_period          DATE,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_plan_version_status CHECK (status IN ('active', 'archived'))
        )
        """
    )

    op.execute(
        "COMMENT ON TABLE plan.plan_versions_metadata IS "
        "'Metadata de gobierno de versiones de proyección. plan_version_key es la llave técnica usada en joins (NO se modifica). display_name es el nombre visible para la UI.'"
    )

    op.execute(
        "COMMENT ON COLUMN plan.plan_versions_metadata.plan_version_key IS "
        "'Llave técnica de versión. Coincide con ops.plan_trips_monthly.plan_version y staging.control_loop_plan_metric_long.plan_version. NO modificar.'"
    )

    op.execute(
        "COMMENT ON COLUMN plan.plan_versions_metadata.display_name IS "
        "'Nombre visible de la versión en la UI. Editable por el usuario.'"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_plan_versions_metadata_status "
        "ON plan.plan_versions_metadata (status)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_plan_versions_metadata_uploaded_at "
        "ON plan.plan_versions_metadata (uploaded_at DESC)"
    )

    # Poblar metadata desde versiones existentes en ops.plan_trips_monthly
    op.execute(
        """
        INSERT INTO plan.plan_versions_metadata (plan_version_key, display_name, source_filename, row_count, uploaded_at, status)
        SELECT
            pv.plan_version,
            pv.plan_version,
            NULL,
            pv.cnt,
            pv.first_at,
            'active'
        FROM (
            SELECT
                plan_version,
                COUNT(*) AS cnt,
                MIN(created_at) AS first_at
            FROM ops.plan_trips_monthly
            GROUP BY plan_version
        ) pv
        ON CONFLICT (plan_version_key) DO NOTHING
        """
    )

    # Poblar metadata desde versiones existentes en staging.control_loop_plan_metric_long
    op.execute(
        """
        INSERT INTO plan.plan_versions_metadata (plan_version_key, display_name, row_count, uploaded_at, status)
        SELECT
            cl.plan_version,
            cl.plan_version,
            cl.cnt,
            cl.first_at,
            'active'
        FROM (
            SELECT
                plan_version,
                COUNT(*) AS cnt,
                MIN(created_at) AS first_at
            FROM staging.control_loop_plan_metric_long
            GROUP BY plan_version
        ) cl
        ON CONFLICT (plan_version_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS plan.plan_versions_metadata")
