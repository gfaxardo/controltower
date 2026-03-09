"""
Real LOB: validación de service_type sin catálogo cerrado.
- Función ops.normalized_service_type (trim, lower, espacios→_, solo alfanumérico y _).
- Función ops.validated_service_type: válido si length<=30, sin coma, ≤3 palabras, alfanumérico/_; si no → UNCLASSIFIED.
- Vista de auditoría ops.v_audit_service_type con service_type_raw, service_type_normalized, viajes, margen_total.
- Métricas: margen_trip y km_prom se calculan siempre como SUM(margen_total)/SUM(viajes) y SUM(km_total)/SUM(viajes).
"""
from alembic import op

revision = "070_real_lob_service_type_validation"
down_revision = "069_real_drill_service_type_tipo_norm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Función normalización: trim, lower, espacios → _, eliminar caracteres no alfanuméricos (permitir _)
    #    Permitir también '-' para tuk-tuk → se convierte a _ para consistencia.
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.normalized_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT regexp_replace(
                regexp_replace(
                    regexp_replace(LOWER(TRIM(COALESCE(raw_value, ''))), '\\s+', '_', 'g'),
                    '-', '_', 'g'
                ),
                '[^a-z0-9_]', '', 'g'
            )
        $$
    """)

    # 2) Validación: length<=10, sin coma, máximo 3 palabras (espacios <= 2), sino UNCLASSIFIED
    #    Palabras: (LENGTH(s) - LENGTH(REPLACE(s, ' ', ''))) + 1; más de 3 palabras → espacios > 2
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.validated_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE
                WHEN raw_value IS NULL OR TRIM(raw_value) = '' THEN 'UNCLASSIFIED'
                WHEN LENGTH(TRIM(raw_value)) > 30 THEN 'UNCLASSIFIED'
                WHEN raw_value LIKE '%,%' THEN 'UNCLASSIFIED'
                WHEN (LENGTH(TRIM(raw_value)) - LENGTH(REPLACE(TRIM(raw_value), ' ', ''))) > 2 THEN 'UNCLASSIFIED'
                WHEN TRIM(raw_value) !~ '^[a-zA-Z0-9_\\s-]+$' THEN 'UNCLASSIFIED'
                ELSE ops.normalized_service_type(raw_value)
            END
        $$
    """)

    # 3) Vista de auditoría: agrega por tipo raw y normalizado (ventana reciente desde trips)
    #    Fuente: v_trips_real_canon; columnas: service_type_raw, service_type_normalized, viajes, margen_total
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_audit_service_type AS
        SELECT
            TRIM(COALESCE(t.tipo_servicio::text, '')) AS service_type_raw,
            ops.validated_service_type(t.tipo_servicio::text) AS service_type_normalized,
            COUNT(*)::bigint AS viajes,
            (-1) * SUM(t.comision_empresa_asociada)::numeric AS margen_total
        FROM ops.v_trips_real_canon t
        WHERE t.condicion = 'Completado'
          AND t.fecha_inicio_viaje IS NOT NULL
          AND t.fecha_inicio_viaje::date >= (CURRENT_DATE - INTERVAL '90 days')::date
          AND t.tipo_servicio IS NOT NULL
        GROUP BY TRIM(COALESCE(t.tipo_servicio::text, '')), ops.validated_service_type(t.tipo_servicio::text)
        ORDER BY viajes DESC
    """)

    # 4) Vista de validación: SUM(viajes) por breakdown debe coincidir con total por (country, period_grain, period_start, segment)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_audit_breakdown_sum AS
        WITH ref AS (
            SELECT country, period_grain, period_start, segment, SUM(trips) AS viajes_total
            FROM ops.real_drill_dim_fact
            WHERE breakdown = 'lob'
            GROUP BY country, period_grain, period_start, segment
        ),
        by_lob AS (SELECT country, period_grain, period_start, segment, SUM(trips) AS s FROM ops.real_drill_dim_fact WHERE breakdown = 'lob' GROUP BY 1,2,3,4),
        by_park AS (SELECT country, period_grain, period_start, segment, SUM(trips) AS s FROM ops.real_drill_dim_fact WHERE breakdown = 'park' GROUP BY 1,2,3,4),
        by_svc AS (SELECT country, period_grain, period_start, segment, SUM(trips) AS s FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type' GROUP BY 1,2,3,4)
        SELECT
            r.country, r.period_grain, r.period_start, r.segment,
            r.viajes_total,
            l.s AS viajes_lob, p.s AS viajes_park, s.s AS viajes_service_type,
            (r.viajes_total = l.s AND r.viajes_total = p.s AND r.viajes_total = s.s) AS breakdown_valid
        FROM ref r
        LEFT JOIN by_lob l ON r.country = l.country AND r.period_grain = l.period_grain AND r.period_start = l.period_start AND r.segment = l.segment
        LEFT JOIN by_park p ON r.country = p.country AND r.period_grain = p.period_grain AND r.period_start = p.period_start AND r.segment = p.segment
        LEFT JOIN by_svc s ON r.country = s.country AND r.period_grain = s.period_grain AND r.period_start = s.period_start AND r.segment = s.segment
        ORDER BY r.country, r.period_grain, r.period_start, r.segment
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_audit_breakdown_sum")
    op.execute("DROP VIEW IF EXISTS ops.v_audit_service_type")
    op.execute("DROP FUNCTION IF EXISTS ops.validated_service_type(text)")
    op.execute("DROP FUNCTION IF EXISTS ops.normalized_service_type(text)")
