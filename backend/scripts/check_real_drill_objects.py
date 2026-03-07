"""
Comprueba existencia y estado de objetos Real Drill (post refactor 068/069).

Comprueba:
- Existencia de ops.real_drill_service_by_park (tabla) y ops.mv_real_drill_service_by_park (vista)
- Existencia de ops.real_drill_dim_fact
- Conteos básicos y freshness (últimas fechas)
- Que existan filas con breakdown='service_type' y que dimension_key no sea solo 'unknown' cuando hay datos
- Query de muestra del drill

Uso: python -m scripts.check_real_drill_objects
Salida: OK/FAIL por chequeo.
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _get_cur():
    from app.db.connection import _get_connection_params
    import psycopg2
    from psycopg2.extras import RealDictCursor

    params = _get_connection_params()
    params["options"] = (params.get("options") or "") + " -c application_name=ct_check_real_drill"
    conn = psycopg2.connect(**params, connect_timeout=10)
    conn.autocommit = True
    return conn.cursor(cursor_factory=RealDictCursor), conn


def _run(check_name: str, ok: bool, detail: str = "") -> None:
    status = "OK" if ok else "FAIL"
    msg = f"  [{status}] {check_name}"
    if detail:
        msg += f" — {detail}"
    print(msg, flush=True)
    return ok


def main() -> None:
    cur, conn = _get_cur()
    all_ok = True

    try:
        # 1. Tabla real_drill_service_by_park existe
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'ops' AND table_name = 'real_drill_service_by_park'
        """)
        exists_table = cur.fetchone() is not None
        all_ok &= _run("Tabla ops.real_drill_service_by_park existe", exists_table)

        # 2. Vista mv_real_drill_service_by_park existe (vista, no MV)
        cur.execute("""
            SELECT 1 FROM information_schema.views
            WHERE table_schema = 'ops' AND table_name = 'mv_real_drill_service_by_park'
        """)
        exists_view = cur.fetchone() is not None
        all_ok &= _run("Vista ops.mv_real_drill_service_by_park existe", exists_view)

        # 3. Tabla real_drill_dim_fact existe
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'ops' AND table_name = 'real_drill_dim_fact'
        """)
        exists_dim = cur.fetchone() is not None
        all_ok &= _run("Tabla ops.real_drill_dim_fact existe", exists_dim)

        if not exists_table or not exists_dim:
            conn.close()
            sys.exit(1)

        # 4. Conteos
        cur.execute("SELECT count(*) AS n FROM ops.real_drill_service_by_park")
        n_park = cur.fetchone()["n"]
        all_ok &= _run("Conteo real_drill_service_by_park", True, f"filas={n_park}")

        cur.execute("SELECT count(*) AS n FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type'")
        n_st = cur.fetchone()["n"]
        all_ok &= _run("Conteo real_drill_dim_fact (breakdown=service_type)", True, f"filas={n_st}")

        # 5. Freshness
        cur.execute("SELECT max(period_start) AS last_period FROM ops.real_drill_service_by_park")
        row = cur.fetchone()
        last_park = row["last_period"] if row and row["last_period"] else None
        _run("Freshness real_drill_service_by_park", True, f"último period_start={last_park}")

        cur.execute("SELECT max(period_start) AS last_period FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type'")
        row = cur.fetchone()
        last_st = row["last_period"] if row and row["last_period"] else None
        _run("Freshness real_drill_dim_fact (service_type)", True, f"último period_start={last_st}")

        # 6. service_type: si hay filas, dimension_key no debe ser solo 'unknown'
        if n_st and n_st > 0:
            cur.execute("""
                SELECT dimension_key, count(*) AS c
                FROM ops.real_drill_dim_fact
                WHERE breakdown = 'service_type'
                GROUP BY dimension_key
            """)
            rows = cur.fetchall()
            keys = [r["dimension_key"] for r in (rows or []) if r.get("dimension_key") not in (None, "unknown")]
            only_unknown = len(keys) == 0
            detail = ", ".join(f"{r['dimension_key']}({r['c']})" for r in (rows or [])[:5])
            all_ok &= _run(
                "service_type con tipos reales (no solo unknown)",
                not only_unknown,
                "dimension_key: " + (detail or "—")
            )
        else:
            _run("service_type con tipos reales (no solo unknown)", True, "sin filas, skip")

        # 7. Query de muestra (drill)
        cur.execute("""
            SELECT country, period_grain, period_start, segment, park_id, city, tipo_servicio_norm, trips
            FROM ops.mv_real_drill_service_by_park
            ORDER BY period_start DESC NULLS LAST, trips DESC NULLS LAST
            LIMIT 3
        """)
        sample = cur.fetchall()
        all_ok &= _run("Query muestra drill (mv_real_drill_service_by_park)", True, f"filas={len(sample)}")
    finally:
        cur.close()
        conn.close()

    print("", flush=True)
    if all_ok:
        print("check_real_drill_objects: todos los chequeos OK.", flush=True)
    else:
        print("check_real_drill_objects: algunos chequeos FAIL.", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
