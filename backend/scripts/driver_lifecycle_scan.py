#!/usr/bin/env python3
"""
[YEGO CONTROL TOWER] SCAN automático para vista Driver Lifecycle.
Fuentes: public.trips_all, public.drivers.
Ejecutar desde backend: python -m scripts.driver_lifecycle_scan [--timeout 300000]
Salida: imprime MAPEO completo y resumen (best_join_key, completion_ts, request_ts, etc.).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

# Timeout por defecto (ms) para consultas pesadas
DEFAULT_TIMEOUT_MS = 300000  # 5 min


def run(cur, sql: str, timeout_ms: int | None = None) -> list:
    if timeout_ms:
        cur.execute(f"SET statement_timeout = '{timeout_ms}'")
    cur.execute(sql)
    return cur.fetchall()


def run_one(cur, sql: str, timeout_ms: int | None = None):
    if timeout_ms:
        cur.execute(f"SET statement_timeout = '{timeout_ms}'")
    cur.execute(sql)
    return cur.fetchone()


def main():
    parser = argparse.ArgumentParser(description="Driver Lifecycle SCAN: trips_all + drivers")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MS, help="Statement timeout in ms")
    args = parser.parse_args()
    timeout = args.timeout

    init_db_pool()
    out_lines = []

    def log(s: str = ""):
        print(s)
        out_lines.append(s)

    log("=" * 80)
    log("A) MAPEO AUTOMÁTICO (SCAN) — Driver Lifecycle")
    log("   Fuentes: public.trips_all, public.drivers")
    log("=" * 80)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SET statement_timeout = '{timeout}'")

        # ----- 1) Esquema y columnas -----
        log("\n--- 1) ESQUEMA Y COLUMNAS ---\n")

        cur.execute("""
            SELECT table_schema, table_name, column_name, data_type, is_nullable,
                   column_default
            FROM information_schema.columns
            WHERE table_name IN ('trips_all', 'drivers')
            AND table_schema = 'public'
            ORDER BY table_schema, table_name, ordinal_position
        """)
        cols = cur.fetchall()
        trips_cols = [c for c in cols if c["table_name"] == "trips_all"]
        drivers_cols = [c for c in cols if c["table_name"] == "drivers"]

        log("public.trips_all:")
        for c in trips_cols:
            log(f"  {c['column_name']:35} {c['data_type']:25} {c['is_nullable']:8} {str(c['column_default'] or '')[:30]}")
        log("")

        log("public.drivers:")
        if not drivers_cols:
            log("  (tabla no encontrada en public)")
        else:
            for c in drivers_cols:
                log(f"  {c['column_name']:35} {c['data_type']:25} {c['is_nullable']:8} {str(c['column_default'] or '')[:30]}")
        log("")

        # Nombres de columnas para uso posterior
        trips_names = [c["column_name"] for c in trips_cols]
        trips_lower = {c["column_name"].lower(): c["column_name"] for c in trips_cols}
        drivers_names = [c["column_name"] for c in drivers_cols]
        drivers_lower = {c["column_name"].lower(): c["column_name"] for c in drivers_cols}

        # ----- 2) Perfilado trips_all -----
        log("\n--- 2) PERFILADO trips_all ---\n")

        try:
            r = run_one(cur, "SELECT COUNT(*) AS cnt FROM public.trips_all", timeout)
            total_trips = r["cnt"] if r else 0
            log(f"COUNT(*): {total_trips:,}")
        except Exception as e:
            log(f"COUNT(*) error: {e}")
            total_trips = 0

        # Driver key candidate
        driver_key_candidates = ["conductor_id", "driver_id", "driver_uuid", "driverid"]
        driver_key_trips = None
        for k in driver_key_candidates:
            if k in trips_lower:
                col = trips_lower[k]
                try:
                    r = run_one(cur, f"SELECT COUNT(DISTINCT \"{col}\") AS cnt FROM public.trips_all WHERE \"{col}\" IS NOT NULL", timeout)
                    log(f"COUNT(DISTINCT {col}): {r['cnt']:,}" if r else f"COUNT(DISTINCT {col}): error")
                    if not driver_key_trips:
                        driver_key_trips = col
                except Exception as e:
                    log(f"  {col}: {e}")
        if not driver_key_trips:
            for c in trips_names:
                if "driver" in c.lower() or "conductor" in c.lower():
                    driver_key_trips = c
                    break
        log(f"Driver key (trips) elegido: {driver_key_trips or 'NO DETECTADO'}")

        # Columnas estado
        state_candidates = ["condicion", "status", "condition", "trip_status", "state"]
        for cn in state_candidates:
            if cn in trips_lower:
                col = trips_lower[cn]
                try:
                    cur.execute(f'SELECT "{col}" AS val, COUNT(*) AS cnt FROM public.trips_all GROUP BY 1 ORDER BY 2 DESC LIMIT 20')
                    rows = cur.fetchall()
                    log(f"Top 20 valores '{col}':")
                    for row in rows:
                        log(f"  {str(row['val']):40} {row['cnt']:,}")
                    break
                except Exception as e:
                    log(f"  {col}: {e}")

        # Columnas tiempo
        ts_types = ("timestamp with time zone", "timestamp without time zone", "date")
        ts_cols = [c for c in trips_cols if c["data_type"] in ts_types or "timestamp" in (c["data_type"] or "").lower() or c["data_type"] == "date"]
        log("\nColumnas de tiempo (MIN/MAX / % nulls):")
        for c in ts_cols:
            col = c["column_name"]
            try:
                cur.execute(f"""
                    SELECT MIN(\"{col}\") AS mn, MAX(\"{col}\") AS mx,
                           COUNT(*) FILTER (WHERE \"{col}\" IS NULL) AS nuls
                    FROM public.trips_all
                """)
                r = cur.fetchone()
                pct = 100.0 * r["nuls"] / total_trips if total_trips else 0
                log(f"  {col}: MIN={r['mn']} MAX={r['mx']} nulls={pct:.2f}%")
            except Exception as e:
                log(f"  {col}: {e}")

        # Dimensiones
        dim_candidates = ["country", "city", "park_id", "tipo_servicio", "service_type", "lob", "segment"]
        log("\nDimensiones (top 20 / % nulls):")
        for cn in dim_candidates:
            if cn in trips_lower:
                col = trips_lower[cn]
                try:
                    cur.execute(f"""
                        SELECT \"{col}\" AS val, COUNT(*) AS cnt
                        FROM public.trips_all GROUP BY 1 ORDER BY 2 DESC LIMIT 20
                    """)
                    rows = cur.fetchall()
                    cur.execute(f'SELECT COUNT(*) FILTER (WHERE \"{col}\" IS NULL) AS n FROM public.trips_all')
                    nuls = cur.fetchone()["n"]
                    pct = 100.0 * nuls / total_trips if total_trips else 0
                    log(f"  {col}: nulls={pct:.2f}% top={[r['val'] for r in rows[:5]]}")
                except Exception as e:
                    log(f"  {col}: {e}")

        # ----- 3) Perfilado drivers -----
        log("\n--- 3) PERFILADO drivers ---\n")
        if not drivers_cols:
            log("Saltando (tabla drivers no existe en public).")
        else:
            try:
                r = run_one(cur, "SELECT COUNT(*) AS cnt FROM public.drivers", timeout)
                total_drivers = r["cnt"] if r else 0
                log(f"COUNT(*): {total_drivers:,}")
            except Exception as e:
                log(f"COUNT(*): {e}")
                total_drivers = 0

            pk_candidates = ["id", "driver_id", "uuid", "driver_uuid"]
            for k in pk_candidates:
                if k in drivers_lower:
                    log(f"PK candidato: {drivers_lower[k]}")
                    break

            ts_driver = [c for c in drivers_cols if c["data_type"] in ts_types or "timestamp" in (c["data_type"] or "").lower() or c["data_type"] == "date"]
            log("Timestamps drivers (MIN/MAX / % nulls):")
            for c in ts_driver:
                col = c["column_name"]
                try:
                    cur.execute(f"""
                        SELECT MIN(\"{col}\") AS mn, MAX(\"{col}\") AS mx,
                               COUNT(*) FILTER (WHERE \"{col}\" IS NULL) AS nuls
                        FROM public.drivers
                    """)
                    r = cur.fetchone()
                    pct = 100.0 * r["nuls"] / total_drivers if total_drivers else 0
                    log(f"  {col}: MIN={r['mn']} MAX={r['mx']} nulls={pct:.2f}%")
                except Exception as e:
                    log(f"  {col}: {e}")

            state_d = [c for c in drivers_cols if "status" in c["column_name"].lower() or "active" in c["column_name"].lower() or "state" in c["column_name"].lower()]
            for c in state_d:
                col = c["column_name"]
                try:
                    cur.execute(f'SELECT \"{col}\" AS val, COUNT(*) AS cnt FROM public.drivers GROUP BY 1 ORDER BY 2 DESC LIMIT 20')
                    rows = cur.fetchall()
                    log(f"Top '{col}': {[(r['val'], r['cnt']) for r in rows[:10]]}")
                except Exception as e:
                    log(f"  {col}: {e}")

        # ----- 4) Join drivers <-> trips_all -----
        log("\n--- 4) JOIN CANDIDATOS (trips_all <-> drivers) ---\n")
        join_candidates = []
        if driver_key_trips and drivers_cols:
            # Candidatos: trips.conductor_id = drivers.id, trips.conductor_id = drivers.driver_id, etc.
            drv_pk = [drivers_lower[k] for k in ["driver_id", "id", "uuid"] if k in drivers_lower]
            for dpk in drv_pk:
                try:
                    cur.execute(f"""
                        SELECT
                            COUNT(*) AS match_count,
                            COUNT(DISTINCT t.\"{driver_key_trips}\") AS distinct_matched
                        FROM public.trips_all t
                        INNER JOIN public.drivers d ON t.\"{driver_key_trips}\" = d.\"{dpk}\"
                    """)
                    r = cur.fetchone()
                    match_count = r["match_count"]
                    distinct_matched = r["distinct_matched"]
                    pct_trips = 100.0 * match_count / total_trips if total_trips else 0
                    join_candidates.append({
                        "trips_col": driver_key_trips,
                        "drivers_col": dpk,
                        "match_count": match_count,
                        "distinct_matched": distinct_matched,
                        "pct_trips_mapped": round(pct_trips, 2),
                    })
                    log(f"  trips.{driver_key_trips} = drivers.{dpk} -> match_count={match_count:,} distinct_drivers={distinct_matched:,} %trips={pct_trips:.2f}%")
                except Exception as e:
                    log(f"  trips.{driver_key_trips} = drivers.{dpk}: {e}")

        best_join = None
        if join_candidates:
            best_join = max(join_candidates, key=lambda x: (x["pct_trips_mapped"], x["match_count"]))
            best_join_key = f"trips.{best_join['trips_col']} = drivers.{best_join['drivers_col']}"
        else:
            best_join_key = f"trips.{driver_key_trips} = drivers.? (sin tabla drivers o sin match)"

        # ----- 5) completion_ts -----
        log("\n--- 5) COMPLETION_TS (timestamp viaje completado) ---\n")
        condicion_col = trips_lower.get("condicion") or trips_lower.get("status") or trips_lower.get("trip_status")
        completion_candidates = []
        for c in ts_cols:
            col = c["column_name"]
            if "fin" in col.lower() or "end" in col.lower() or "complet" in col.lower():
                completion_candidates.insert(0, col)
            elif "inicio" in col.lower() or "start" in col.lower() or "fecha" in col.lower():
                completion_candidates.append(col)
        if not completion_candidates:
            completion_candidates = [c["column_name"] for c in ts_cols]

        completion_ts_candidate = None
        if condicion_col:
            try:
                cur.execute(f"SELECT \"{condicion_col}\" AS val FROM public.trips_all WHERE \"{condicion_col}\" IS NOT NULL LIMIT 1")
                sample = cur.fetchone()
                completed_value = "Completado"  # valor típico en codebase
                for cand in completion_candidates:
                    col = cand
                    cur.execute(f"""
                        SELECT MIN(\"{col}\") AS mn, MAX(\"{col}\") AS mx,
                               COUNT(*) FILTER (WHERE \"{col}\" IS NOT NULL) AS non_null
                        FROM public.trips_all
                        WHERE LOWER(TRIM(\"{condicion_col}\"::text)) LIKE '%complet%'
                           OR LOWER(TRIM(\"{condicion_col}\"::text)) LIKE '%finish%'
                           OR LOWER(TRIM(\"{condicion_col}\"::text)) LIKE '%done%'
                    """)
                    r = cur.fetchone()
                    if r and r["non_null"] and r["non_null"] > 0:
                        completion_ts_candidate = col
                        log(f"  completion_ts candidato (filtrando completados): {col} non_null={r['non_null']:,}")
                        break
            except Exception as e:
                log(f"  Error filtrando por condicion: {e}")
        if not completion_ts_candidate and ts_cols:
            completion_ts_candidate = ts_cols[0]["column_name"]
            log(f"  completion_ts por defecto (primera columna tiempo): {completion_ts_candidate}")

        # ----- 6) request_ts -----
        log("\n--- 6) REQUEST_TS (creación/solicitud trip) ---\n")
        request_candidates = [trips_lower.get(k) for k in ["fecha_inicio_viaje", "created_at", "requested_at", "accepted_at", "assigned_at", "start_time"] if trips_lower.get(k)]
        request_ts_candidate = None
        for col in request_candidates:
            if col and col != completion_ts_candidate:
                request_ts_candidate = col
                log(f"  request_ts candidato: {col}")
                break
        if not request_ts_candidate and completion_ts_candidate:
            request_ts_candidate = completion_ts_candidate
            log("  request_ts = completion_ts (mismo timestamp usado como proxy)")

        # ----- 7) activation + drivers registered/approved -----
        log("\n--- 7) ACTIVATION + registered_ts / approved_ts (drivers) ---\n")
        registered_ts = drivers_lower.get("registered_at") or drivers_lower.get("created_at") or drivers_lower.get("registration_date")
        approved_ts = drivers_lower.get("approved_at") or drivers_lower.get("activated_at")
        if registered_ts:
            log(f"  drivers.registered_ts: {registered_ts}")
        else:
            log("  drivers.registered_ts: NO ENCONTRADO")
        if approved_ts:
            log(f"  drivers.approved_ts: {approved_ts}")
        else:
            log("  drivers.approved_ts: NO ENCONTRADO")

        # ----- RESUMEN FINAL -----
        log("\n" + "=" * 80)
        log("RESUMEN SCAN")
        log("=" * 80)
        log(f"  best_join_key:        {best_join_key}")
        log(f"  completion_ts:        {completion_ts_candidate or 'N/A'}")
        log(f"  request_ts:           {request_ts_candidate or 'N/A'}")
        log(f"  driver_key (trips):   {driver_key_trips or 'N/A'}")
        log(f"  driver_registered_ts: {registered_ts or 'N/A'}")
        log(f"  driver_approved_ts:   {approved_ts or 'N/A'}")
        dims = [cn for cn in dim_candidates if cn in trips_lower]
        log(f"  dimensiones (trips):  {dims}")
        log("=" * 80)

        cur.close()

    # Opcional: guardar a archivo
    out_path = os.path.join(os.path.dirname(__file__), "..", "driver_lifecycle_scan_output.txt")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines))
        print(f"\nSalida guardada en: {out_path}")
    except Exception as e:
        print(f"\nNo se pudo guardar salida: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
