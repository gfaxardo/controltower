"""
CT-HOURLY-FIRST-FINAL-UNIFICATION: real_rollup_day_fact deja de ser tabla poblada por backfill
y pasa a ser vista derivada de ops.mv_real_lob_day_v2.
Preserva contrato de columnas para real_lob_daily_service, comparative_metrics_service,
real_lob_drill_pro_service, v_real_data_coverage, v_real_lob_coverage.
"""
from alembic import op

revision = "101_real_rollup_from_day_v2"
down_revision = "100_real_operational_freshness"
branch_labels = None
depends_on = None

# Vista que mapea day_v2 al esquema de real_rollup_day_fact (trips=completados, b2b_trips, margin, etc.)
SQL_V_REAL_ROLLUP_FROM_DAY_V2 = """
CREATE OR REPLACE VIEW ops.v_real_rollup_day_from_day_v2 AS
SELECT
    trip_date AS trip_day,
    country,
    city,
    park_id,
    COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text, '') AS park_name_resolved,
    CASE WHEN park_id IS NOT NULL AND TRIM(COALESCE(park_id,'')) <> '' THEN 'OK' ELSE 'SIN_PARK' END AS park_bucket,
    lob_group,
    segment_tag,
    SUM(completed_trips)::bigint AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint AS b2b_trips,
    SUM(margin_total) AS margin_total_raw,
    ABS(SUM(margin_total)) AS margin_total_pos,
    CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END AS margin_unit_pos,
    SUM(distance_total_km) AS distance_total_km,
    CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL
         THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END AS km_prom,
    MAX(max_trip_ts) AS last_trip_ts
FROM ops.mv_real_lob_day_v2
GROUP BY trip_date, country, city, park_id, park_name, lob_group, segment_tag
"""


def upgrade() -> None:
    # 1) Crear vista intermedia desde day_v2
    op.execute("DROP VIEW IF EXISTS ops.v_real_rollup_day_from_day_v2 CASCADE")
    op.execute(SQL_V_REAL_ROLLUP_FROM_DAY_V2)

    # 2) Quitar dependencias de la tabla para poder sustituirla por vista
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_rollup_day CASCADE")

    # 3) Sustituir tabla por vista con mismo nombre y contrato
    op.execute("DROP TABLE IF EXISTS ops.real_rollup_day_fact CASCADE")
    op.execute("""
        CREATE VIEW ops.real_rollup_day_fact AS
        SELECT * FROM ops.v_real_rollup_day_from_day_v2
    """)
    op.execute("COMMENT ON VIEW ops.real_rollup_day_fact IS 'Derivado de mv_real_lob_day_v2 (hourly-first). Reemplaza tabla poblada por backfill legacy.'")

    # 4) Recrear vistas de compatibilidad
    op.execute("CREATE VIEW ops.mv_real_rollup_day AS SELECT * FROM ops.real_rollup_day_fact")
    op.execute("""
        CREATE VIEW ops.v_real_lob_coverage AS
        SELECT
            (SELECT MIN(trip_day) FROM ops.real_rollup_day_fact) AS min_trip_date_loaded,
            (SELECT MAX(trip_day) FROM ops.real_rollup_day_fact) AS max_trip_date_loaded,
            120 AS recent_days_config,
            NOW() AS computed_at
    """)
    op.execute("""
        CREATE VIEW ops.v_real_data_coverage AS
        SELECT
            country,
            MIN(trip_day) AS min_trip_date,
            MAX(trip_day) AS last_trip_date,
            MAX(last_trip_ts) AS last_trip_ts,
            date_trunc('month', MIN(trip_day))::date AS min_month,
            date_trunc('week', MIN(trip_day))::date AS min_week,
            date_trunc('month', MAX(trip_day))::date AS last_month_with_data,
            date_trunc('week', MAX(trip_day))::date AS last_week_with_data
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe')
        GROUP BY country
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_rollup_day CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.real_rollup_day_fact CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_rollup_day_from_day_v2 CASCADE")
    # Restaurar tabla real_rollup_day_fact requiere recrear con CREATE TABLE y repoblar con backfill_real_lob_mvs (no se hace aquí).
    raise NotImplementedError(
        "Downgrade 101: real_rollup_day_fact era vista; para volver atrás hay que recrear la tabla (064) y ejecutar backfill_real_lob_mvs."
    )
