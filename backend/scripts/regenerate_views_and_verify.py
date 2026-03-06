"""
Regenera/refresca vistas y MVs que necesita el frontend y verifica que respondan.

Uso:
  cd backend && python -m scripts.regenerate_views_and_verify
  python -m scripts.regenerate_views_and_verify --skip-refresh   # solo verificar
  python -m scripts.regenerate_views_and_verify --refresh-driver --refresh-supply

Hace:
  1. Lista MVs en ops y las refresca (salvo las que son vistas en 064).
  2. Opcional: refresh driver lifecycle y supply (--refresh-driver, --refresh-supply).
  3. Verifica que cada objeto crítico para el front exista y sea consultable.
"""
import argparse
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# Objetos que el frontend usa (vista o MV). name -> (schema, object_name, tipo esperado 'view'|'matview'|'table')
FRONTEND_OBJECTS = [
    # Core / Plan / Real
    ("ops.mv_real_trips_monthly", "Plan vs Real mensual, Real monthly"),
    ("ops.v_plan_vs_real_realkey_final", "Plan vs Real alerts"),
    ("ops.v_plan_trips_monthly_latest", "Plan monthly"),
    ("plan.plan_long", "Plan datos"),
    # Real LOB (064: vistas sobre fact)
    ("ops.mv_real_drill_dim_agg", "Real LOB Drill (vista sobre real_drill_dim_fact)"),
    ("ops.mv_real_rollup_day", "Real LOB Drill rollup (vista sobre real_rollup_day_fact)"),
    ("ops.v_real_data_coverage", "Real LOB coverage"),
    ("ops.real_drill_dim_fact", "Real LOB drill fact table"),
    ("ops.real_rollup_day_fact", "Real LOB rollup fact table"),
    # Real LOB legacy (pueden ser MVs)
    ("ops.mv_real_trips_by_lob_month", "Real LOB monthly"),
    ("ops.mv_real_trips_by_lob_week", "Real LOB weekly"),
    ("ops.mv_real_trips_weekly", "Phase2B weekly"),
    # Driver Lifecycle
    ("ops.mv_driver_lifecycle_base", "Driver Lifecycle base"),
    ("ops.mv_driver_weekly_stats", "Driver Lifecycle weekly"),
    ("ops.mv_driver_segments_weekly", "Driver Lifecycle segments"),
    # Supply
    ("ops.mv_supply_segments_weekly", "Supply segments"),
    ("ops.mv_supply_alerts_weekly", "Supply alerts"),
    # Phase2c / otros
    ("ops.mv_driver_monthly_stats", "Driver monthly"),
]


def _get_conn():
    from app.settings import settings
    import psycopg2
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        options="-c statement_timeout=0",
    )


def _object_exists_and_type(cur, qualified_name):
    """Retorna 'view', 'matview', 'table' o None si no existe."""
    parts = qualified_name.split(".", 1)
    if len(parts) != 2:
        return None
    schema, name = parts
    cur.execute("""
        SELECT 'view' FROM pg_views WHERE schemaname = %s AND viewname = %s
        UNION ALL
        SELECT 'matview' FROM pg_matviews WHERE schemaname = %s AND matviewname = %s
        UNION ALL
        SELECT 'table' FROM pg_tables WHERE schemaname = %s AND tablename = %s
    """, (schema, name, schema, name, schema, name))
    row = cur.fetchone()
    return row[0] if row else None


def refresh_matviews_in_ops(cur, skip_views):
    """Refresca todas las MVs del schema ops que sean materialized (no vistas)."""
    cur.execute("""
        SELECT schemaname || '.' || matviewname AS name
        FROM pg_matviews
        WHERE schemaname = 'ops'
        ORDER BY matviewname
    """)
    mvs = [r[0] for r in cur.fetchall()]
    # En 064, mv_real_drill_dim_agg y mv_real_rollup_day son vistas; no estarán en pg_matviews.
    for mv in mvs:
        if skip_views and mv in ("ops.mv_real_drill_dim_agg", "ops.mv_real_rollup_day"):
            continue
        try:
            logger.info("Refrescando %s...", mv)
            cur.execute("SET work_mem = '256MB'")
            try:
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}")
                logger.info("  %s OK (CONCURRENTLY)", mv)
            except Exception as e:
                if "concurrent" in (str(e) or "").lower() or "unique" in (str(e) or "").lower():
                    conn = cur.connection
                    if hasattr(conn, "rollback"):
                        conn.rollback()
                    cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
                    logger.info("  %s OK (sin CONCURRENTLY)", mv)
                else:
                    raise
        except Exception as e:
            logger.warning("  %s falló: %s", mv, e)


def verify_object(cur, qualified_name, description, timeout_sec=15):
    """Verifica que el objeto exista y sea consultable. Retorna (ok, msg)."""
    obj_type = _object_exists_and_type(cur, qualified_name)
    if not obj_type:
        return False, f"No existe"
    try:
        cur.execute(f"SELECT 1 FROM {qualified_name} LIMIT 1")
        cur.fetchone()
        return True, f"OK ({obj_type})"
    except Exception as e:
        return False, str(e)[:80]


def main():
    parser = argparse.ArgumentParser(description="Regenera vistas/MVs y verifica frontend")
    parser.add_argument("--skip-refresh", action="store_true", help="Solo verificar, no refrescar MVs")
    parser.add_argument("--refresh-driver", action="store_true", help="Ejecutar refresh driver lifecycle")
    parser.add_argument("--refresh-supply", action="store_true", help="Ejecutar refresh supply MVs")
    args = parser.parse_args()

    conn = _get_conn()
    conn.autocommit = True
    cur = conn.cursor()

    print("=" * 80)
    print("1) REFRESH DE MATERIALIZED VIEWS (ops)")
    print("=" * 80)
    if not args.skip_refresh:
        refresh_matviews_in_ops(cur, skip_views=True)
    else:
        print("  (omitido por --skip-refresh)")

    if args.refresh_driver:
        print("\n" + "=" * 80)
        print("2) REFRESH DRIVER LIFECYCLE")
        print("=" * 80)
        try:
            import subprocess
            r = subprocess.run(
                [sys.executable, "-m", "scripts.check_driver_lifecycle_and_validate"],
                cwd=BACKEND_DIR,
                timeout=3600,
                capture_output=True,
                text=True,
            )
            if r.returncode == 0:
                print("  Driver lifecycle refresh OK")
            else:
                logger.warning("Driver lifecycle: returncode=%s stderr=%s", r.returncode, r.stderr[:500] if r.stderr else "")
        except Exception as e:
            logger.warning("Driver lifecycle refresh: %s", e)

    if args.refresh_supply:
        print("\n" + "=" * 80)
        print("3) REFRESH SUPPLY MVs")
        print("=" * 80)
        try:
            from app.services.supply_service import refresh_supply_alerting_mvs
            refresh_supply_alerting_mvs()
            print("  Supply refresh OK")
        except Exception as e:
            logger.warning("Supply refresh: %s", e)

    print("\n" + "=" * 80)
    print("VERIFICACIÓN DE OBJETOS PARA EL FRONTEND")
    print("=" * 80)
    print(f"{'Objeto':<45} {'Estado':<30} {'Uso'}")
    print("-" * 100)
    failed = []
    for qualified_name, description in FRONTEND_OBJECTS:
        ok, msg = verify_object(cur, qualified_name, description)
        status = "OK" if ok else "FALLO"
        if not ok:
            failed.append((qualified_name, msg))
        print(f"{qualified_name:<45} {status:<10} {msg:<20}  {description}")
    print("-" * 100)

    cur.close()
    conn.close()

    if failed:
        print("\nObjetos con fallo:")
        for name, msg in failed:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    print("\nTodos los objetos verificados correctamente.")
    sys.exit(0)


if __name__ == "__main__":
    main()
