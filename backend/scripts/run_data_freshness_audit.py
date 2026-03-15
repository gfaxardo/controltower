"""
Freshness & Coverage: ejecuta el chequeo de freshness y escribe en ops.data_freshness_audit.
Diseñado para ser ligero: consultas acotadas a ventana reciente (RECENT_DAYS) para evitar full scans.
Status: OK | PARTIAL_EXPECTED | LAGGING | MISSING_EXPECTED_DATA | SOURCE_STALE | DERIVED_STALE
Uso: cd backend && python -m scripts.run_data_freshness_audit
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from psycopg2 import sql as pg_sql
from psycopg2.extras import RealDictCursor

# Ventana para MAX(): solo considerar datos recientes (evita full scan en tablas enormes)
RECENT_DAYS = int(os.environ.get("DATA_FRESHNESS_RECENT_DAYS", "180"))


def _parse_object(obj: str | None) -> tuple[str, str]:
    """Convierte 'schema.table' -> (schema, table)."""
    if not obj or not obj.strip():
        return "public", ""
    s = obj.strip()
    if "." in s:
        schema, table = s.split(".", 1)
        return schema.strip(), table.strip()
    return "public", s


def _safe_max_date(
    conn,
    schema: str,
    table: str,
    date_column: str,
    bounded: bool = True,
) -> date | None:
    """
    MAX(date_column)::date. Si bounded=True, filtra date_column >= current_date - RECENT_DAYS
    para usar índice y evitar full scan.
    """
    if not table or not date_column:
        return None
    try:
        if bounded:
            # Filtro por ventana reciente para usar índice y evitar full scan
            q = pg_sql.SQL("""
                SELECT MAX({col})::date AS mx FROM {sch}.{tbl}
                WHERE {col} >= current_date - {days}
            """).format(
                col=pg_sql.Identifier(date_column),
                sch=pg_sql.Identifier(schema),
                tbl=pg_sql.Identifier(table),
                days=pg_sql.Literal(RECENT_DAYS),
            )
        else:
            q = pg_sql.SQL("SELECT MAX({})::date AS mx FROM {}.{}").format(
                pg_sql.Identifier(date_column),
                pg_sql.Identifier(schema),
                pg_sql.Identifier(table),
            )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(q)
        row = cur.fetchone()
        cur.close()
        if row and row.get("mx"):
            return row["mx"] if isinstance(row["mx"], date) else date.fromisoformat(str(row["mx"])[:10])
        return None
    except Exception as e:
        print(f"  [WARN] MAX({date_column}) FROM {schema}.{table}: {e}", file=sys.stderr)
        return None


def _expected_latest_for_grain(grain: str, expected_delay_days: int) -> date:
    """expected_latest_date: daily = current_date - 1; weekly = última semana cerrada; monthly = último mes cerrado."""
    today = date.today()
    if grain == "day":
        return today - timedelta(days=expected_delay_days)
    if grain == "week":
        last_monday = today - timedelta(days=today.weekday())
        last_sunday = last_monday - timedelta(days=1)
        return last_sunday
    if grain == "month":
        first_this = today.replace(day=1)
        return first_this - timedelta(days=1)
    return today - timedelta(days=expected_delay_days)


def _compute_status(
    derived_max_date: date | None,
    source_max_date: date | None,
    expected_latest: date,
    grain: str,
    alert_threshold_days: int | None,
) -> tuple[str, str]:
    """
    OK | PARTIAL_EXPECTED | LAGGING | MISSING_EXPECTED_DATA | SOURCE_STALE | DERIVED_STALE
    """
    effective_max = derived_max_date if derived_max_date is not None else source_max_date
    if effective_max is None:
        return "MISSING_EXPECTED_DATA", "No se pudo obtener fecha máxima en fuente ni derivado"

    missing_days = (expected_latest - effective_max).days if effective_max < expected_latest else 0
    lag_days = None
    if source_max_date is not None and derived_max_date is not None and derived_max_date < source_max_date:
        lag_days = (source_max_date - derived_max_date).days

    # Fuente por debajo de lo esperado
    if source_max_date is not None and source_max_date < expected_latest:
        d = (expected_latest - source_max_date).days
        if d >= (alert_threshold_days or 2):
            return "SOURCE_STALE", f"Fuente con data hasta {source_max_date}; se esperaba hasta {expected_latest}"

    # Derivado atrasado respecto a la fuente (DERIVED_STALE / LAGGING)
    if lag_days is not None and lag_days > 0:
        return "DERIVED_STALE", f"Derivado atrasado {lag_days} días (fuente hasta {source_max_date}, derivado hasta {derived_max_date})"

    # Falta data esperada (effective por debajo de expected)
    if missing_days > 0:
        threshold = alert_threshold_days or 2
        if missing_days >= threshold:
            return "MISSING_EXPECTED_DATA", f"Se esperaba data hasta {expected_latest}; último dato {effective_max} (faltan {missing_days} días)"
        return "PARTIAL_EXPECTED", f"Periodo abierto o retraso menor: esperado hasta {expected_latest}, último {effective_max}"

    return "OK", ""


def main() -> None:
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    print(f"Ventana reciente: {RECENT_DAYS} días (DATA_FRESHNESS_RECENT_DAYS)")
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT dataset_name, grain, expected_delay_days, source_object, source_date_column,
                   derived_object, derived_date_column, alert_threshold_days
            FROM ops.data_freshness_expectations
            WHERE active = true
            ORDER BY dataset_name
        """)
        rows = cur.fetchall()
        cur.close()

        if not rows:
            print("No hay expectativas activas en ops.data_freshness_expectations.")
            return

        ins = conn.cursor()
        for r in rows:
            dataset_name = r["dataset_name"]
            grain = r["grain"] or "day"
            expected_delay = int(r["expected_delay_days"] or 1)
            alert_threshold = r["alert_threshold_days"]
            src_col = r["source_date_column"] or "fecha_inicio_viaje"
            source_obj = r["source_object"]

            schema_s, table_s = _parse_object(source_obj)
            # Evitar vistas pesadas (v_trips_real_canon): usar tablas base con bounded query
            if table_s and ("v_trips_real_canon" in (source_obj or "") or "v_trips_real_canon_120d" in (source_obj or "") or "v_driver_lifecycle_trips" in (source_obj or "")):
                # Fuente canónica = max de tablas base (trips_all, trips_2026) o vista liviana
                if "v_trips_real_canon" in (source_obj or "") or "v_trips_real_canon_120d" in (source_obj or ""):
                    ma = _safe_max_date(conn, "public", "trips_all", "fecha_inicio_viaje", bounded=True)
                    m6 = _safe_max_date(conn, "public", "trips_2026", "fecha_inicio_viaje", bounded=True)
                    source_max = max(d for d in (ma, m6) if d is not None) if (ma or m6) else None
                else:
                    source_max = _safe_max_date(conn, schema_s, table_s, src_col, bounded=True)
            else:
                source_max = _safe_max_date(conn, schema_s, table_s, src_col, bounded=True) if table_s else None

            derived_max = None
            if r["derived_object"]:
                schema_d, table_d = _parse_object(r["derived_object"])
                col = (r["derived_date_column"] or "period_start").strip()
                if table_d and col:
                    derived_max = _safe_max_date(conn, schema_d, table_d, col, bounded=True)

            expected_latest = _expected_latest_for_grain(grain, expected_delay)
            effective_max = derived_max or source_max
            if effective_max is not None:
                missing_days = max(0, (expected_latest - effective_max).days) if effective_max < expected_latest else 0
            else:
                missing_days = None

            lag_days = None
            if source_max and derived_max and derived_max < source_max:
                lag_days = (source_max - derived_max).days

            status, alert_reason = _compute_status(
                derived_max, source_max, expected_latest, grain, alert_threshold
            )

            ins.execute("""
                INSERT INTO ops.data_freshness_audit
                (dataset_name, source_object, derived_object, grain, source_max_date, derived_max_date,
                 expected_latest_date, lag_days, missing_expected_days, status, alert_reason, checked_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            """, (
                dataset_name,
                r["source_object"],
                r["derived_object"],
                grain,
                source_max,
                derived_max,
                expected_latest,
                lag_days,
                missing_days,
                status,
                alert_reason or None,
            ))
            print(f"  {dataset_name}: source_max={source_max} derived_max={derived_max} expected={expected_latest} status={status}")

        conn.commit()
        ins.close()
    print("Auditoría escrita en ops.data_freshness_audit.")


if __name__ == "__main__":
    main()
