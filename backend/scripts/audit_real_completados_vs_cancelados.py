"""
Auditoría semántica: completados vs cancelados sobre trips_2025 + trips_2026.
Fuentes oficiales según SOURCE_OF_TRUTH_REAL_AUDIT_V2.md.

READ-ONLY: No modifica datos. Solo consulta y genera reporte.

Uso:
    cd backend
    python -m scripts.audit_real_completados_vs_cancelados
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db_audit
from psycopg2.extras import RealDictCursor
from datetime import datetime


def run_query(conn, sql, params=None):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params or ())
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def print_table(title, rows, columns=None):
    if not rows:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
        print("  (sin datos)")
        return
    if columns is None:
        columns = list(rows[0].keys())
    col_widths = {}
    for col in columns:
        col_widths[col] = max(len(str(col)), max(len(str(r.get(col, ""))) for r in rows))
    header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
    sep = "-+-".join("-" * col_widths[col] for col in columns)
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"  {header}")
    print(f"  {sep}")
    for r in rows:
        line = " | ".join(str(r.get(col, "")).ljust(col_widths[col]) for col in columns)
        print(f"  {line}")


def phase2_schema_inspection(conn):
    """Inspecciona columnas de trips_2025 y trips_2026."""
    sql = """
    SELECT table_name, column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name IN ('trips_2025', 'trips_2026')
      AND column_name IN (
          'id', 'park_id', 'tipo_servicio', 'fecha_inicio_viaje',
          'fecha_finalizacion', 'comision_empresa_asociada', 'pago_corporativo',
          'distancia_km', 'condicion', 'conductor_id', 'motivo_cancelacion',
          'precio_yango_pro', 'comision_servicio', 'efectivo', 'tarjeta'
      )
    ORDER BY table_name, column_name
    """
    return run_query(conn, sql)


def phase2_condicion_values(conn):
    """Valores distintos de condicion en cada tabla."""
    sql = """
    SELECT 'trips_2025' AS tabla, condicion, COUNT(*) AS total
    FROM public.trips_2025
    GROUP BY condicion
    ORDER BY total DESC
    """
    rows_2025 = run_query(conn, sql)

    sql2 = """
    SELECT 'trips_2026' AS tabla, condicion, COUNT(*) AS total
    FROM public.trips_2026
    GROUP BY condicion
    ORDER BY total DESC
    """
    rows_2026 = run_query(conn, sql2)
    return rows_2025 + rows_2026


def phase2_monthly_breakdown(conn):
    """Conteo mensual por estado del viaje."""
    sql = """
    WITH combined AS (
        SELECT
            'trips_2025' AS source_table,
            date_trunc('month', fecha_inicio_viaje)::date AS mes,
            CASE
                WHEN condicion = 'Completado' THEN 'completado'
                WHEN condicion = 'Cancelado' OR lower(condicion) LIKE '%%cancel%%' THEN 'cancelado'
                ELSE 'otro'
            END AS estado
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
        UNION ALL
        SELECT
            'trips_2026' AS source_table,
            date_trunc('month', fecha_inicio_viaje)::date AS mes,
            CASE
                WHEN condicion = 'Completado' THEN 'completado'
                WHEN condicion = 'Cancelado' OR lower(condicion) LIKE '%%cancel%%' THEN 'cancelado'
                ELSE 'otro'
            END AS estado
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
    )
    SELECT
        source_table,
        mes,
        COUNT(*) AS total_trips,
        COUNT(*) FILTER (WHERE estado = 'completado') AS completed,
        COUNT(*) FILTER (WHERE estado = 'cancelado') AS cancelled,
        COUNT(*) FILTER (WHERE estado = 'otro') AS other
    FROM combined
    GROUP BY source_table, mes
    ORDER BY source_table, mes
    """
    return run_query(conn, sql)


def phase2_coverage_completed(conn):
    """Cobertura de campos críticos SOLO sobre completados, por tabla y mes."""
    sql = """
    WITH completed AS (
        SELECT
            'trips_2025' AS source_table,
            date_trunc('month', fecha_inicio_viaje)::date AS mes,
            comision_empresa_asociada,
            precio_yango_pro,
            conductor_id,
            park_id,
            tipo_servicio,
            fecha_inicio_viaje,
            fecha_finalizacion
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
          AND condicion = 'Completado'
        UNION ALL
        SELECT
            'trips_2026' AS source_table,
            date_trunc('month', fecha_inicio_viaje)::date AS mes,
            comision_empresa_asociada,
            precio_yango_pro,
            conductor_id,
            park_id,
            tipo_servicio,
            fecha_inicio_viaje,
            fecha_finalizacion
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
          AND condicion = 'Completado'
    )
    SELECT
        source_table,
        mes,
        COUNT(*) AS total_completed,
        COUNT(comision_empresa_asociada) AS con_comision,
        ROUND(100.0 * COUNT(comision_empresa_asociada) / NULLIF(COUNT(*), 0), 2) AS pct_comision,
        COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL AND comision_empresa_asociada != 0) AS con_comision_nonzero,
        ROUND(100.0 * COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL AND comision_empresa_asociada != 0) / NULLIF(COUNT(*), 0), 2) AS pct_comision_nonzero,
        COUNT(precio_yango_pro) AS con_ticket,
        ROUND(100.0 * COUNT(precio_yango_pro) / NULLIF(COUNT(*), 0), 2) AS pct_ticket,
        COUNT(conductor_id) AS con_driver,
        ROUND(100.0 * COUNT(conductor_id) / NULLIF(COUNT(*), 0), 2) AS pct_driver,
        COUNT(park_id) AS con_park,
        ROUND(100.0 * COUNT(park_id) / NULLIF(COUNT(*), 0), 2) AS pct_park,
        COUNT(tipo_servicio) AS con_tipo_srv,
        ROUND(100.0 * COUNT(tipo_servicio) / NULLIF(COUNT(*), 0), 2) AS pct_tipo_srv,
        COUNT(fecha_finalizacion) AS con_fecha_fin,
        ROUND(100.0 * COUNT(fecha_finalizacion) / NULLIF(COUNT(*), 0), 2) AS pct_fecha_fin
    FROM completed
    GROUP BY source_table, mes
    ORDER BY source_table, mes
    """
    return run_query(conn, sql)


def phase2_coverage_cancelled(conn):
    """Cobertura de campos sobre cancelados."""
    sql = """
    WITH cancelled AS (
        SELECT
            'trips_2025' AS source_table,
            date_trunc('month', fecha_inicio_viaje)::date AS mes,
            motivo_cancelacion,
            park_id,
            tipo_servicio,
            conductor_id
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
          AND (condicion = 'Cancelado' OR lower(condicion) LIKE '%%cancel%%')
        UNION ALL
        SELECT
            'trips_2026' AS source_table,
            date_trunc('month', fecha_inicio_viaje)::date AS mes,
            motivo_cancelacion,
            park_id,
            tipo_servicio,
            conductor_id
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
          AND (condicion = 'Cancelado' OR lower(condicion) LIKE '%%cancel%%')
    )
    SELECT
        source_table,
        mes,
        COUNT(*) AS total_cancelled,
        COUNT(motivo_cancelacion) AS con_motivo,
        ROUND(100.0 * COUNT(motivo_cancelacion) / NULLIF(COUNT(*), 0), 2) AS pct_motivo,
        COUNT(park_id) AS con_park,
        ROUND(100.0 * COUNT(park_id) / NULLIF(COUNT(*), 0), 2) AS pct_park,
        COUNT(tipo_servicio) AS con_tipo_srv,
        ROUND(100.0 * COUNT(tipo_servicio) / NULLIF(COUNT(*), 0), 2) AS pct_tipo_srv,
        COUNT(conductor_id) AS con_driver,
        ROUND(100.0 * COUNT(conductor_id) / NULLIF(COUNT(*), 0), 2) AS pct_driver
    FROM cancelled
    GROUP BY source_table, mes
    ORDER BY source_table, mes
    """
    return run_query(conn, sql)


def phase2_comision_diagnostic(conn):
    """Diagnóstico: comision_empresa_asociada sobre TODO el universo vs solo completados."""
    sql = """
    WITH all_trips AS (
        SELECT
            'trips_2025' AS src,
            condicion,
            comision_empresa_asociada
        FROM public.trips_2025
        WHERE fecha_inicio_viaje IS NOT NULL
        UNION ALL
        SELECT
            'trips_2026' AS src,
            condicion,
            comision_empresa_asociada
        FROM public.trips_2026
        WHERE fecha_inicio_viaje IS NOT NULL
    )
    SELECT
        src,
        CASE
            WHEN condicion = 'Completado' THEN 'completado'
            WHEN condicion = 'Cancelado' OR lower(condicion) LIKE '%%cancel%%' THEN 'cancelado'
            ELSE 'otro'
        END AS estado,
        COUNT(*) AS total,
        COUNT(comision_empresa_asociada) AS con_comision,
        ROUND(100.0 * COUNT(comision_empresa_asociada) / NULLIF(COUNT(*), 0), 2) AS pct_con_comision,
        COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL AND comision_empresa_asociada != 0) AS con_comision_nonzero,
        ROUND(100.0 * COUNT(*) FILTER (WHERE comision_empresa_asociada IS NOT NULL AND comision_empresa_asociada != 0) / NULLIF(COUNT(*), 0), 2) AS pct_nonzero
    FROM all_trips
    GROUP BY src, 2
    ORDER BY src, 2
    """
    return run_query(conn, sql)


def main():
    print("=" * 70)
    print("  AUDITORÍA SEMÁNTICA: COMPLETADOS VS CANCELADOS")
    print(f"  Fuentes: public.trips_2025 + public.trips_2026")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Modo: READ-ONLY")
    print("=" * 70)

    with get_db_audit(timeout_ms=900000) as conn:
        print("\n[1/6] Inspeccionando schema de trips_2025 y trips_2026...")
        schema = phase2_schema_inspection(conn)
        print_table("SCHEMA: Columnas críticas", schema,
                     ["table_name", "column_name", "data_type", "is_nullable"])

        print("\n[2/6] Valores de condicion por tabla...")
        condicion = phase2_condicion_values(conn)
        print_table("VALORES DE condicion", condicion,
                     ["tabla", "condicion", "total"])

        print("\n[3/6] Conteo mensual por estado...")
        monthly = phase2_monthly_breakdown(conn)
        print_table("CONTEO MENSUAL POR ESTADO", monthly,
                     ["source_table", "mes", "total_trips", "completed", "cancelled", "other"])

        print("\n[4/6] Cobertura de campos sobre COMPLETADOS...")
        cov_completed = phase2_coverage_completed(conn)
        print_table("COBERTURA SOBRE COMPLETADOS (comision, ticket, driver, park, tipo_srv, fecha_fin)",
                     cov_completed,
                     ["source_table", "mes", "total_completed",
                      "pct_comision", "pct_comision_nonzero",
                      "pct_ticket", "pct_driver", "pct_park",
                      "pct_tipo_srv", "pct_fecha_fin"])

        print("\n[5/6] Cobertura de campos sobre CANCELADOS...")
        cov_cancelled = phase2_coverage_cancelled(conn)
        print_table("COBERTURA SOBRE CANCELADOS (motivo, park, tipo_srv, driver)",
                     cov_cancelled,
                     ["source_table", "mes", "total_cancelled",
                      "pct_motivo", "pct_park", "pct_tipo_srv", "pct_driver"])

        print("\n[6/6] Diagnóstico comision_empresa_asociada: todo el universo vs completados...")
        diag = phase2_comision_diagnostic(conn)
        print_table("DIAGNÓSTICO COMISION: UNIVERSO TOTAL VS SOLO COMPLETADOS",
                     diag,
                     ["src", "estado", "total", "con_comision",
                      "pct_con_comision", "con_comision_nonzero", "pct_nonzero"])

        # Veredicto
        print("\n" + "=" * 70)
        print("  VEREDICTO AUTOMÁTICO")
        print("=" * 70)

        completados_comision = [r for r in diag if r["estado"] == "completado"]
        cancelados_comision = [r for r in diag if r["estado"] == "cancelado"]

        for r in completados_comision:
            pct = float(r.get("pct_nonzero") or 0)
            src = r["src"]
            if pct > 50:
                print(f"  [{src}] COMPLETADOS: comision_empresa_asociada nonzero = {pct}% → "
                      f"COBERTURA ACEPTABLE sobre completados")
            elif pct > 5:
                print(f"  [{src}] COMPLETADOS: comision_empresa_asociada nonzero = {pct}% → "
                      f"COBERTURA PARCIAL — investigar períodos específicos")
            else:
                print(f"  [{src}] COMPLETADOS: comision_empresa_asociada nonzero = {pct}% → "
                      f"PROBLEMA REAL: comisión ausente en completados")

        for r in cancelados_comision:
            pct = float(r.get("pct_nonzero") or 0)
            src = r["src"]
            print(f"  [{src}] CANCELADOS: comision_empresa_asociada nonzero = {pct}% → "
                  f"{'ESPERADO (cancelados no tienen comisión)' if pct < 10 else 'ANOMALÍA: cancelados con comisión'}")

        total_all = sum(int(r.get("total", 0)) for r in diag)
        total_comp = sum(int(r.get("total", 0)) for r in completados_comision)
        total_canc = sum(int(r.get("total", 0)) for r in cancelados_comision)
        comision_all = sum(int(r.get("con_comision_nonzero", 0)) for r in diag)
        comision_comp = sum(int(r.get("con_comision_nonzero", 0)) for r in completados_comision)

        pct_all = round(100.0 * comision_all / total_all, 2) if total_all else 0
        pct_comp = round(100.0 * comision_comp / total_comp, 2) if total_comp else 0

        print(f"\n  RESUMEN:")
        print(f"  - Total viajes (todo universo): {total_all:,}")
        print(f"  - Completados: {total_comp:,} | Cancelados: {total_canc:,}")
        print(f"  - Comisión nonzero sobre TODO: {pct_all}%")
        print(f"  - Comisión nonzero sobre COMPLETADOS: {pct_comp}%")

        if pct_comp > pct_all * 1.5:
            print(f"\n  → CONCLUSIÓN: El null masivo previo de comision_empresa_asociada se debe")
            print(f"    MAYORMENTE a que el chequeo se hizo sobre todo el universo incluyendo cancelados.")
            print(f"    Al filtrar solo completados, la cobertura sube de {pct_all}% a {pct_comp}%.")
            print(f"    VEREDICTO: (A) Auditoría previa estaba mal hecha sobre universo bruto.")
        else:
            print(f"\n  → CONCLUSIÓN: El problema de comision_empresa_asociada persiste")
            print(f"    incluso al filtrar solo completados ({pct_comp}% vs {pct_all}% sobre todo).")
            print(f"    VEREDICTO: (B) Hay un hueco real en completados.")

    print(f"\n  Auditoría completada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
