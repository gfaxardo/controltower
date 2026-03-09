"""
Vista de observabilidad: service_type no mapeados (is_unclassified) para detectar nuevos candidatos a mapping.
- ops.v_real_service_type_unmapped_monitor: agregado por (tipo_servicio_raw, tipo_servicio_norm) últimos 90 días,
  solo filas con is_unclassified = true. Incluye trips, first_seen_date, last_seen_date, sample_lob_resolved.
"""
from alembic import op

revision = "071_real_service_type_unmapped_monitor"
down_revision = "070_canonical_service_type_lob"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_service_type_unmapped_monitor CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_service_type_unmapped_monitor AS
        SELECT
            tipo_servicio_raw,
            tipo_servicio_norm,
            COUNT(*)::bigint AS trips,
            MIN(fecha_inicio_viaje)::date AS first_seen_date,
            MAX(fecha_inicio_viaje)::date AS last_seen_date,
            'UNCLASSIFIED'::text AS sample_lob_resolved,
            true AS is_unclassified
        FROM ops.v_real_trips_service_lob_resolved
        WHERE is_unclassified = true
          AND fecha_inicio_viaje::date >= (current_date - 90)
        GROUP BY tipo_servicio_raw, tipo_servicio_norm
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_service_type_unmapped_monitor IS
        'Observabilidad: service_type no mapeados (últimos 90 días). Consultar con ORDER BY trips DESC para priorizar candidatos a mapping.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_service_type_unmapped_monitor CASCADE")
