"""
Real LOB Drill: desglose tipo_servicio por park para filtro rápido.
- Solo DDL: tabla ops.real_drill_service_by_park + vista ops.mv_real_drill_service_by_park (compatibilidad).
- El llenado de datos se hace con scripts/backfill_real_drill_service_by_park.py (fuera de Alembic).
"""
from alembic import op

revision = "068_real_drill_service_by_park_mv"
down_revision = "067_mv_driver_segments_weekly_join_config"
branch_labels = None
depends_on = None

TABLE_NAME = "ops.real_drill_service_by_park"
VIEW_NAME = "ops.mv_real_drill_service_by_park"


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_drill_service_by_park CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_drill_service_by_park CASCADE")
    op.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            country text NOT NULL,
            period_grain text NOT NULL,
            period_start date NOT NULL,
            segment text NOT NULL,
            park_id text,
            city text,
            tipo_servicio_norm text,
            trips bigint NOT NULL,
            margin_total numeric,
            margin_per_trip numeric,
            km_avg numeric,
            b2b_trips bigint,
            b2b_share numeric,
            last_trip_ts timestamptz
        )
    """)
    op.execute(f"""
        COMMENT ON TABLE {TABLE_NAME} IS
        'Desglose por (country, period, segment, park, city, tipo_servicio_norm). Poblado por scripts/backfill_real_drill_service_by_park.py.'
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX uq_real_drill_service_by_park
        ON {TABLE_NAME} (country, period_grain, period_start, segment, COALESCE(park_id,''), COALESCE(city,''), COALESCE(tipo_servicio_norm,''))
    """)
    op.execute(f"""
        CREATE INDEX idx_real_drill_svc_by_park_lookup
        ON {TABLE_NAME} (country, period_grain, period_start, park_id)
    """)
    op.execute(f"""
        CREATE VIEW {VIEW_NAME} AS SELECT * FROM {TABLE_NAME}
    """)
    op.execute(f"""
        COMMENT ON VIEW {VIEW_NAME} IS
        'Compatibilidad: mismo nombre y esquema que la MV anterior. Lee de tabla real_drill_service_by_park.'
    """)


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {VIEW_NAME} CASCADE")
    op.execute(f"DROP TABLE IF EXISTS {TABLE_NAME} CASCADE")
