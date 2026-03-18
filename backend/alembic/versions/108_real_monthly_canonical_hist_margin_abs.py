"""Corrige margin en mv_real_monthly_canonical_hist: usar ABS(comision_empresa_asociada) para revenue (fuente puede ser negativo)."""
from alembic import op

revision = "108_real_monthly_canonical_hist_margin_abs"
down_revision = "107_real_monthly_canonical_hist_mv"
branch_labels = None
depends_on = None

# Misma definición que 107 pero margin_total = ABS(COALESCE(comision_empresa_asociada, 0))
SQL_MV = """
CREATE MATERIALIZED VIEW ops.mv_real_monthly_canonical_hist AS
WITH canon AS (
    SELECT id, park_id, fecha_inicio_viaje, fecha_finalizacion, comision_empresa_asociada, condicion, conductor_id
    FROM ops.v_trips_real_canon
    WHERE fecha_inicio_viaje IS NOT NULL
),
with_park AS (
    SELECT ct.*, p.name AS park_name_raw, p.city AS park_city_raw
    FROM canon ct
    LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(ct.park_id::text))
),
with_geo AS (
    SELECT wp.id, wp.fecha_inicio_viaje, wp.condicion, wp.conductor_id, wp.comision_empresa_asociada,
        CASE
            WHEN wp.park_name_raw::text ILIKE '%%cali%%' OR wp.park_name_raw::text ILIKE '%%bogot%%'
                OR wp.park_name_raw::text ILIKE '%%barranquilla%%' OR wp.park_name_raw::text ILIKE '%%medell%%'
                OR wp.park_name_raw::text ILIKE '%%cucut%%' OR wp.park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'co'
            WHEN wp.park_name_raw::text ILIKE '%%lima%%' OR TRIM(COALESCE(wp.park_name_raw::text, '')) = 'Yego'
                OR wp.park_name_raw::text ILIKE '%%arequip%%' OR wp.park_name_raw::text ILIKE '%%trujill%%' THEN 'pe'
            ELSE ''
        END AS country
    FROM with_park wp
),
base AS (
    SELECT
        DATE_TRUNC('month', wp.fecha_inicio_viaje)::date AS month_start,
        country,
        (condicion = 'Completado') AS is_completed,
        conductor_id,
        ABS(COALESCE(comision_empresa_asociada, 0))::numeric AS margin_total
    FROM with_geo wp
)
SELECT month_start, country,
    SUM(CASE WHEN is_completed THEN 1 ELSE 0 END)::bigint AS trips,
    SUM(CASE WHEN is_completed THEN margin_total ELSE 0 END)::numeric AS margin_total,
    COUNT(DISTINCT CASE WHEN is_completed AND conductor_id IS NOT NULL THEN conductor_id END)::bigint AS active_drivers_core
FROM base
GROUP BY month_start, country
WITH NO DATA
"""


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_monthly_canonical_hist CASCADE")
    op.execute(SQL_MV)
    op.execute("COMMENT ON MATERIALIZED VIEW ops.mv_real_monthly_canonical_hist IS 'Canónica mensual REAL histórica. margin_total = ABS(comision_empresa_asociada). Refrescar tras 108.'")
    op.execute("CREATE UNIQUE INDEX uq_mv_real_monthly_canonical_hist ON ops.mv_real_monthly_canonical_hist (month_start, country)")
    op.execute("CREATE INDEX idx_mv_real_monthly_hist_year ON ops.mv_real_monthly_canonical_hist (EXTRACT(YEAR FROM month_start), country)")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_monthly_canonical_hist CASCADE")
    # Recrear 107 (GREATEST) requiere volver a 107
