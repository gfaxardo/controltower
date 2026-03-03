"""
FASE 0 — SCAN: Inspección de columnas y tipos para trips_all, trips_2026, drivers, dim.dim_park.
Detecta: driver id, park_id, timestamp viaje, condicion/estado.
Comprueba si trips_all contiene filas 2026 (MAX(fecha)).
Ejecutar: cd backend && python -m scripts.scan_trips_drivers_parks_schema
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db

TIMEOUT_MS = 120000


def run(cursor, sql, params=None, description=""):
    try:
        cursor.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    except Exception as e:
        print(f"  [ERROR] {description}: {e}")
        return None


def columns_info(cursor, schema: str, table: str):
    """Columnas y tipos de (schema, table)."""
    r = run(
        cursor,
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
        f"columns {schema}.{table}",
    )
    return r or []


def main():
    print("=" * 60)
    print("FASE 0 — SCAN: trips_all, trips_2026, drivers, dim.dim_park")
    print("=" * 60)

    with get_db() as conn:
        cur = conn.cursor()

        # 1) public.trips_all
        print("\n--- 1) public.trips_all ---")
        cols = columns_info(cur, "public", "trips_all")
        if not cols:
            print("  Tabla no encontrada o sin columnas.")
        else:
            for c in cols:
                print(f"  {c[0]}: {c[1]} (nullable={c[2]})")
            # Candidatos
            names = [c[0].lower() for c in cols]
            driver_cand = [c[0] for c in cols if "driver" in c[0].lower() or "conductor" in c[0].lower()]
            park_cand = [c[0] for c in cols if "park" in c[0].lower()]
            ts_cand = [c[0] for c in cols if any(x in c[0].lower() for x in ("fecha", "date", "timestamp", "inicio", "fin", "complet"))]
            cond_cand = [c[0] for c in cols if any(x in c[0].lower() for x in ("condicion", "estado", "status", "state"))]
            print("  Candidatos driver_id:", driver_cand or "ninguno")
            print("  Candidatos park_id:", park_cand or "ninguno")
            print("  Candidatos timestamp viaje:", ts_cand or "ninguno")
            print("  Candidatos condicion/estado:", cond_cand or "ninguno")
            # Top valores condicion si existe
            cond_col = (cond_cand or [None])[0]
            if cond_col:
                top = run(
                    cur,
                    f"SELECT {cond_col}, COUNT(*) FROM public.trips_all WHERE {cond_col} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10",
                    description=f"top {cond_col}",
                )
                if top:
                    print(f"  Top valores '{cond_col}':", [(r[0], r[1]) for r in top])
            # MAX(fecha) para detectar 2026
            fecha_col = None
            for c in cols:
                if c[0].lower() in ("fecha_inicio_viaje", "fecha_inicio", "trip_date", "date"):
                    fecha_col = c[0]
                    break
            if not fecha_col and ts_cand:
                fecha_col = ts_cand[0]
            if fecha_col:
                mx = run(cur, f"SELECT MAX({fecha_col}) FROM public.trips_all", description="max fecha trips_all")
                if mx and mx[0][0]:
                    print(f"  MAX({fecha_col}):", mx[0][0], "-> trips_all TIENE 2026" if str(mx[0][0])[:4] == "2026" else "-> trips_all NO tiene 2026")
                else:
                    print(f"  MAX({fecha_col}): (vacío o error)")

        # 2) public.trips_2026
        print("\n--- 2) public.trips_2026 ---")
        exists_2026 = run(
            cur,
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'trips_2026'",
            description="exists trips_2026",
        )
        if not exists_2026:
            print("  Tabla no existe. Crear con misma estructura que trips_all antes de VIEW unificada.")
        else:
            cols = columns_info(cur, "public", "trips_2026")
            for c in cols:
                print(f"  {c[0]}: {c[1]} (nullable={c[2]})")
            driver_cand = [c[0] for c in cols if "driver" in c[0].lower() or "conductor" in c[0].lower()]
            park_cand = [c[0] for c in cols if "park" in c[0].lower()]
            print("  Candidatos driver_id:", driver_cand or "ninguno")
            print("  Candidatos park_id:", park_cand or "ninguno")

        # 3) public.drivers
        print("\n--- 3) public.drivers ---")
        cols = columns_info(cur, "public", "drivers")
        if not cols:
            print("  Tabla no encontrada.")
        else:
            for c in cols:
                print(f"  {c[0]}: {c[1]} (nullable={c[2]})")
            driver_cand = [c[0] for c in cols if "driver" in c[0].lower() or "id" == c[0].lower()]
            park_cand = [c[0] for c in cols if "park" in c[0].lower()]
            print("  Candidatos driver_id:", driver_cand or "ninguno")
            print("  Candidatos park_id:", park_cand or "ninguno")

        # 4) dim.dim_park (schema dim, table dim_park)
        print("\n--- 4) dim.dim_park ---")
        cols = columns_info(cur, "dim", "dim_park")
        if not cols:
            print("  Tabla no encontrada (schema dim, table dim_park).")
        else:
            for c in cols:
                print(f"  {c[0]}: {c[1]} (nullable={c[2]})")
            park_id_col = [c[0] for c in cols if c[0].lower() in ("park_id", "id")]
            name_col = [c[0] for c in cols if "name" in c[0].lower() or "nombre" in c[0].lower()]
            print("  Candidatos park_id:", park_id_col or "ninguno")
            print("  Candidatos park_name:", name_col or "ninguno")

        cur.close()

    print("\n--- Fin FASE 0 ---")
    print("Usar resultado para: VIEW trips_unified (corte 2026 si trips_all tiene 2026), índices por nombres reales.")


if __name__ == "__main__":
    main()
