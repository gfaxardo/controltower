"""
Re-enlazar ops.mv_real_lob_hour_v2 (y derivados day/week/month) a ops.v_real_trip_fact_v2.

Problema: despliegues que usaron bootstrap_hourly_first.py dejaron la MV definida como
SELECT ... FROM ops.staging_bootstrap_mv_real_lob_hour_v2. Tras datos congelados en staging,
REFRESH MATERIALIZED VIEW no incorpora viajes nuevos desde el canon vivo.

Solución: DROP CASCADE en orden inverso de dependencias y recrear las cuatro MV con la
definición oficial (099) leyendo de v_real_trip_fact_v2. CREATE ... AS SELECT rellena
en el upgrade (puede tardar; statement_timeout=0 en la sesión de migración).

Nota: CASCADE puede eliminar vistas que dependían de day_v2 (p. ej. real_rollup_day_fact).
La migración 136 las restaura.

down_revision: 134 (post-merge de ramas 133_*).
"""
from alembic import op
from sqlalchemy import text

revision = "135_fix_hourly_first_mv_source_live_fact"
down_revision = "134_merge_133_heads_ct_gov1_slice_governance"
branch_labels = None
depends_on = None

SQL_MV_HOUR = """
CREATE MATERIALIZED VIEW ops.mv_real_lob_hour_v2 AS
SELECT
    trip_date,
    trip_hour,
    country,
    city,
    park_id,
    park_name,
    lob_group,
    real_tipo_servicio_norm,
    segment_tag,
    trip_outcome_norm,
    cancel_reason_norm,
    cancel_reason_group,
    COUNT(*) AS requested_trips,
    COUNT(*) FILTER (WHERE is_completed) AS completed_trips,
    COUNT(*) FILTER (WHERE is_cancelled) AS cancelled_trips,
    COUNT(*) FILTER (WHERE NOT is_completed AND NOT is_cancelled) AS unknown_outcome_trips,
    SUM(gross_revenue) AS gross_revenue,
    SUM(margin_total) AS margin_total,
    SUM(distance_km) AS distance_total_km,
    SUM(trip_duration_minutes) AS duration_total_minutes,
    AVG(trip_duration_minutes) AS duration_avg_minutes,
    CASE WHEN COUNT(*) > 0
        THEN ROUND((COUNT(*) FILTER (WHERE is_cancelled))::numeric / COUNT(*)::numeric, 4)
        ELSE 0 END AS cancellation_rate,
    CASE WHEN COUNT(*) > 0
        THEN ROUND((COUNT(*) FILTER (WHERE is_completed))::numeric / COUNT(*)::numeric, 4)
        ELSE 0 END AS completion_rate,
    MAX(fecha_inicio_viaje) AS max_trip_ts
FROM ops.v_real_trip_fact_v2
GROUP BY
    trip_date, trip_hour, country, city, park_id, park_name,
    lob_group, real_tipo_servicio_norm, segment_tag,
    trip_outcome_norm, cancel_reason_norm, cancel_reason_group
"""

SQL_MV_DAY = """
CREATE MATERIALIZED VIEW ops.mv_real_lob_day_v2 AS
SELECT
    trip_date,
    country,
    city,
    park_id,
    park_name,
    lob_group,
    real_tipo_servicio_norm,
    segment_tag,
    trip_outcome_norm,
    cancel_reason_norm,
    cancel_reason_group,
    SUM(requested_trips) AS requested_trips,
    SUM(completed_trips) AS completed_trips,
    SUM(cancelled_trips) AS cancelled_trips,
    SUM(unknown_outcome_trips) AS unknown_outcome_trips,
    SUM(gross_revenue) AS gross_revenue,
    SUM(margin_total) AS margin_total,
    SUM(distance_total_km) AS distance_total_km,
    SUM(duration_total_minutes) AS duration_total_minutes,
    CASE WHEN SUM(completed_trips) > 0
        THEN ROUND(SUM(duration_total_minutes) / SUM(completed_trips)::numeric, 2)
        ELSE NULL END AS duration_avg_minutes,
    CASE WHEN SUM(requested_trips) > 0
        THEN ROUND(SUM(cancelled_trips)::numeric / SUM(requested_trips)::numeric, 4)
        ELSE 0 END AS cancellation_rate,
    CASE WHEN SUM(requested_trips) > 0
        THEN ROUND(SUM(completed_trips)::numeric / SUM(requested_trips)::numeric, 4)
        ELSE 0 END AS completion_rate,
    MAX(max_trip_ts) AS max_trip_ts
FROM ops.mv_real_lob_hour_v2
GROUP BY
    trip_date, country, city, park_id, park_name,
    lob_group, real_tipo_servicio_norm, segment_tag,
    trip_outcome_norm, cancel_reason_norm, cancel_reason_group
"""

SQL_MV_WEEK = """
CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v3 AS
WITH hourly AS (SELECT * FROM ops.mv_real_lob_hour_v2),
global_max AS (SELECT MAX(max_trip_ts) AS m FROM hourly)
SELECT
    DATE_TRUNC('week', h.trip_date)::date AS week_start,
    h.country,
    h.city,
    h.park_id,
    h.park_name,
    h.lob_group,
    h.real_tipo_servicio_norm,
    h.segment_tag,
    SUM(h.requested_trips) AS trips,
    SUM(h.completed_trips) AS completed_trips,
    SUM(h.cancelled_trips) AS cancelled_trips,
    SUM(h.gross_revenue) AS revenue,
    SUM(h.margin_total) AS margin_total,
    SUM(h.distance_total_km) AS distance_total_km,
    SUM(h.duration_total_minutes) AS duration_total_minutes,
    MAX(h.max_trip_ts) AS max_trip_ts,
    (DATE_TRUNC('week', h.trip_date)::date = DATE_TRUNC('week', g.m)::date) AS is_open
FROM hourly h
CROSS JOIN global_max g
GROUP BY
    DATE_TRUNC('week', h.trip_date)::date,
    h.country, h.city, h.park_id, h.park_name,
    h.lob_group, h.real_tipo_servicio_norm, h.segment_tag,
    (DATE_TRUNC('week', h.trip_date)::date = DATE_TRUNC('week', g.m)::date)
"""

SQL_MV_MONTH = """
CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v3 AS
WITH hourly AS (SELECT * FROM ops.mv_real_lob_hour_v2),
global_max AS (SELECT MAX(max_trip_ts) AS m FROM hourly)
SELECT
    DATE_TRUNC('month', h.trip_date)::date AS month_start,
    h.country,
    h.city,
    h.park_id,
    h.park_name,
    h.lob_group,
    h.real_tipo_servicio_norm,
    h.segment_tag,
    SUM(h.requested_trips) AS trips,
    SUM(h.completed_trips) AS completed_trips,
    SUM(h.cancelled_trips) AS cancelled_trips,
    SUM(h.gross_revenue) AS revenue,
    SUM(h.margin_total) AS margin_total,
    SUM(h.distance_total_km) AS distance_total_km,
    SUM(h.duration_total_minutes) AS duration_total_minutes,
    MAX(h.max_trip_ts) AS max_trip_ts,
    (DATE_TRUNC('month', h.trip_date)::date = DATE_TRUNC('month', g.m)::date) AS is_open
FROM hourly h
CROSS JOIN global_max g
GROUP BY
    DATE_TRUNC('month', h.trip_date)::date,
    h.country, h.city, h.park_id, h.park_name,
    h.lob_group, h.real_tipo_servicio_norm, h.segment_tag,
    (DATE_TRUNC('month', h.trip_date)::date = DATE_TRUNC('month', g.m)::date)
"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("SET statement_timeout = 0"))
    conn.execute(text("SET lock_timeout = 0"))

    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v3 CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v3 CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_day_v2 CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_hour_v2 CASCADE")

    op.execute(SQL_MV_HOUR)
    op.execute(
        """CREATE UNIQUE INDEX uq_mv_real_lob_hour_v2
        ON ops.mv_real_lob_hour_v2 (
            trip_date, trip_hour, country, city, park_id,
            lob_group, real_tipo_servicio_norm, segment_tag,
            trip_outcome_norm,
            COALESCE(cancel_reason_norm, ''),
            COALESCE(cancel_reason_group, '')
        )"""
    )
    op.execute("CREATE INDEX idx_mv_hour_v2_date ON ops.mv_real_lob_hour_v2 (trip_date)")
    op.execute("CREATE INDEX idx_mv_hour_v2_country_date ON ops.mv_real_lob_hour_v2 (country, trip_date)")
    op.execute("CREATE INDEX idx_mv_hour_v2_hour ON ops.mv_real_lob_hour_v2 (trip_hour)")
    op.execute("CREATE INDEX idx_mv_hour_v2_lob ON ops.mv_real_lob_hour_v2 (lob_group, segment_tag)")

    op.execute(SQL_MV_DAY)
    op.execute(
        """CREATE UNIQUE INDEX uq_mv_real_lob_day_v2
        ON ops.mv_real_lob_day_v2 (
            trip_date, country, city, park_id,
            lob_group, real_tipo_servicio_norm, segment_tag,
            trip_outcome_norm,
            COALESCE(cancel_reason_norm, ''),
            COALESCE(cancel_reason_group, '')
        )"""
    )
    op.execute("CREATE INDEX idx_mv_day_v2_country_date ON ops.mv_real_lob_day_v2 (country, trip_date)")
    op.execute("CREATE INDEX idx_mv_day_v2_lob ON ops.mv_real_lob_day_v2 (lob_group, segment_tag)")

    op.execute(SQL_MV_WEEK)
    op.execute(
        """CREATE UNIQUE INDEX uq_mv_real_lob_week_v3
        ON ops.mv_real_lob_week_v3 (
            country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start
        )"""
    )
    op.execute("CREATE INDEX idx_mv_week_v3_ccpw ON ops.mv_real_lob_week_v3 (country, city, park_id, week_start)")
    op.execute("CREATE INDEX idx_mv_week_v3_ls ON ops.mv_real_lob_week_v3 (lob_group, segment_tag)")

    op.execute(SQL_MV_MONTH)
    op.execute(
        """CREATE UNIQUE INDEX uq_mv_real_lob_month_v3
        ON ops.mv_real_lob_month_v3 (
            country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start
        )"""
    )
    op.execute("CREATE INDEX idx_mv_month_v3_ccpm ON ops.mv_real_lob_month_v3 (country, city, park_id, month_start)")
    op.execute("CREATE INDEX idx_mv_month_v3_ls ON ops.mv_real_lob_month_v3 (lob_group, segment_tag)")

    op.execute(
        "COMMENT ON MATERIALIZED VIEW ops.mv_real_lob_hour_v2 IS "
        "'Agregado horario REAL (hourly-first). Fuente: ops.v_real_trip_fact_v2. "
        "REFRESH debe leer el fact vivo, no staging_bootstrap.'"
    )


def downgrade() -> None:
    raise NotImplementedError(
        "No se revierte automáticamente: restaurar desde backup o re-ejecutar bootstrap si aplica."
    )
