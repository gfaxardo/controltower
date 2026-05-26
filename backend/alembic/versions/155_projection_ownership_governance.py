"""
155 — Projection Ownership Governance (Fase 0.1)

Crea la tabla formal ops.projection_ownership para persistencia gobernada
de ownership de proyecciones, separada de staging y de la tabla canónica.

  - jefe_producto TEXT NULL   (responsable de la línea)
  - estado       TEXT NULL   (validado sin cambios | validado con cambios | por validar)

NO modifica:
  - ops.plan_trips_monthly
  - staging.control_loop_plan_metric_long
  - MVs / Omniview / Plan vs Real

Estrategia: deduplicación por dimensiones (country + city + lob), no por métricas.
Un índice único garantiza un registro de ownership por combinación dimensional.

down_revision: 154_projection_ownership_compatibility
"""

from alembic import op

revision = "155_projection_ownership_governance"
down_revision = "154_projection_ownership_compatibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.projection_ownership (
            id                  BIGSERIAL PRIMARY KEY,
            plan_version_key    TEXT NOT NULL,
            country             TEXT,
            city                TEXT,
            city_norm           TEXT,
            linea_negocio_canonica TEXT NOT NULL,
            jefe_producto       TEXT,
            producto            TEXT,
            estado              TEXT,
            source_upload_id    TEXT,
            source_period_first DATE,
            source_row_hash     TEXT,
            conflict_detected   BOOLEAN NOT NULL DEFAULT FALSE,
            conflict_detail     JSONB,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_projection_ownership_key
        ON ops.projection_ownership (
            plan_version_key,
            COALESCE(country, ''),
            COALESCE(city, ''),
            linea_negocio_canonica
        )
        """
    )
    op.execute(
        "COMMENT ON TABLE ops.projection_ownership IS "
        "'Fase 0.1 — Ownership governance: responsable + estado por plan_version/country/city/LOB. "
        "NO incluye métricas. NO se expone en Omniview todavía.'"
    )
    op.execute(
        """
        COMMENT ON COLUMN ops.projection_ownership.jefe_producto IS
        'Nombre del Jefe Producto responsable de la línea de negocio en esta versión de plan'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN ops.projection_ownership.estado IS
        'Estado de validación: validado sin cambios | validado con cambios | por validar'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_projection_ownership_plan_version
        ON ops.projection_ownership (plan_version_key)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_projection_ownership_jefe
        ON ops.projection_ownership (jefe_producto)
        WHERE jefe_producto IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ops.uq_projection_ownership_key")
    op.execute("DROP TABLE IF EXISTS ops.projection_ownership CASCADE")
