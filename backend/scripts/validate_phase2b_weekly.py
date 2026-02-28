#!/usr/bin/env python3
"""
Validaciones Fase 2B (semanal):
- Unicidad MV semanal
- Reconciliacion semanal vs trips_all (ultima semana cerrada)
- Sanity (signos de revenue/commission)
- Plan semanal suma a plan mensual

Usa engine propio (pool_size=2, max_overflow=0), statement_timeout 10min y dispose al final.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Timeout para queries largas (reconciliacion, etc.)
STATEMENT_TIMEOUT = "10min"


def _get_database_url():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    from app.settings import settings
    return settings.database_url


def _is_timeout_error(e):
    """Detecta si la excepcion es por statement timeout (QueryCanceled / 57014)."""
    msg = str(e).lower()
    if "timeout" in msg or "57014" in msg or "querycanceled" in msg or "canceling statement" in msg:
        return True
    try:
        import psycopg2
        if e.__class__.__name__ == "QueryCanceled":
            return True
    except Exception:
        pass
    return False


def validate_uniqueness(conn):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        print("\n" + "=" * 80)
        print("8.1 VALIDACION: Unicidad MV semanal")
        print("=" * 80)
        cursor.execute("""
            SELECT week_start, country, city_norm, lob_base, segment, COUNT(*) as cnt
            FROM ops.mv_real_trips_weekly
            GROUP BY 1,2,3,4,5
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC, week_start DESC
            LIMIT 20;
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"\n  [ERROR] Encontrados {len(rows)} grupos con duplicados:")
            for row in rows:
                print(f"    - {row['week_start']} | {row['country']} | {row['city_norm']} | {row['lob_base']} | {row['segment']} ({row['cnt']} veces)")
            return False
        print("\n  [OK] Unicidad garantizada (0 duplicados)")
        return True
    finally:
        cursor.close()


def validate_reconciliation(conn):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        print("\n" + "=" * 80)
        print("8.2 VALIDACION: Reconciliacion semanal (ultima semana cerrada)")
        print("=" * 80)
        cursor.execute("SELECT DATE_TRUNC('week', NOW())::DATE - INTERVAL '1 week' as week_start;")
        week_start = cursor.fetchone()['week_start']
        print(f"\n  Semana a reconciliar: {week_start}")

        cursor.execute("""
            WITH direct_sum AS (
                SELECT
                    DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE as week_start,
                    COALESCE(dp.country, '') as country,
                    -1 * SUM(NULLIF(t.comision_empresa_asociada, 0)) as revenue_real_yego_direct
                FROM public.trips_all t
                LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
                WHERE t.condicion = 'Completado'
                  AND DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE = %s
                GROUP BY 1,2
            ),
            mv_sum AS (
                SELECT
                    week_start,
                    country,
                    SUM(revenue_real_yego) as revenue_real_yego_mv
                FROM ops.mv_real_trips_weekly
                WHERE week_start = %s
                GROUP BY 1,2
            )
            SELECT
                COALESCE(d.week_start, m.week_start) as week_start,
                COALESCE(d.country, m.country) as country,
                COALESCE(d.revenue_real_yego_direct, 0) as revenue_real_yego_direct,
                COALESCE(m.revenue_real_yego_mv, 0) as revenue_real_yego_mv,
                ABS(COALESCE(d.revenue_real_yego_direct, 0) - COALESCE(m.revenue_real_yego_mv, 0)) as diff
            FROM direct_sum d
            FULL OUTER JOIN mv_sum m
              ON d.week_start = m.week_start AND d.country = m.country
            ORDER BY country;
        """, (week_start, week_start))

        rows = cursor.fetchall()
        all_ok = True
        for row in rows:
            diff = row['diff'] or 0
            print(f"\n  Pais: {row['country']}")
            print(f"    Direct (trips_all): {row['revenue_real_yego_direct']:.2f}")
            print(f"    MV revenue_real_yego: {row['revenue_real_yego_mv']:.2f}")
            print(f"    Diff: {diff:.4f}")
            if diff > 0.01:
                print("    [ERROR] Diferencia > 0.01")
                all_ok = False
            else:
                print("    [OK] Reconciliacion correcta")
        return all_ok
    finally:
        cursor.close()


def validate_sanity(conn):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        print("\n" + "=" * 80)
        print("8.3 VALIDACION: Sanity checks")
        print("=" * 80)

        cursor.execute("""
            SELECT COUNT(*) as negative_revenue_count
            FROM ops.mv_real_trips_weekly
            WHERE revenue_real_yego < 0;
        """)
        negative_revenue = cursor.fetchone()['negative_revenue_count'] or 0
        print(f"\n  revenue_real_yego < 0: {negative_revenue}")

        cursor.execute("""
            SELECT COUNT(*) as positive_commission_count
            FROM ops.mv_real_trips_weekly
            WHERE commission_yego_signed > 0;
        """)
        positive_commission = cursor.fetchone()['positive_commission_count'] or 0
        print(f"  commission_yego_signed > 0: {positive_commission}")

        if positive_commission > 0:
            cursor.execute("""
                SELECT week_start, country, city_norm, lob_base, segment, commission_yego_signed
                FROM ops.mv_real_trips_weekly
                WHERE commission_yego_signed > 0
                ORDER BY week_start DESC
                LIMIT 10;
            """)
            samples = cursor.fetchall()
            print("\n  Ejemplos (commission positiva):")
            for s in samples:
                print(f"    - {s['week_start']} | {s['country']} | {s['city_norm']} | {s['lob_base']} | {s['segment']} | {s['commission_yego_signed']}")

        return negative_revenue == 0
    finally:
        cursor.close()


def validate_plan_weekly_sum(conn):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        print("\n" + "=" * 80)
        print("8.4 VALIDACION: Plan semanal suma a plan mensual")
        print("=" * 80)
        cursor.execute("""
            WITH plan_weekly AS (
                SELECT
                    DATE_TRUNC('month', week_start)::DATE as month,
                    country,
                    city_norm,
                    lob_base,
                    segment,
                    SUM(trips_plan_week) as trips_plan_week_sum,
                    SUM(drivers_plan_week) as drivers_plan_week_sum,
                    SUM(revenue_plan_week) as revenue_plan_week_sum
                FROM ops.v_plan_trips_weekly_from_monthly
                GROUP BY 1,2,3,4,5
            ),
            plan_monthly AS (
                SELECT
                    month,
                    country,
                    COALESCE(plan_city_resolved_norm, city_norm) as city_norm,
                    lob_base,
                    segment,
                    SUM(projected_trips) as trips_plan_month,
                    SUM(projected_drivers) as drivers_plan_month,
                    SUM(projected_revenue) as revenue_plan_month
                FROM ops.v_plan_trips_monthly_latest
                GROUP BY 1,2,3,4,5
            )
            SELECT
                COALESCE(w.month, m.month) as month,
                COALESCE(w.country, m.country) as country,
                COALESCE(w.city_norm, m.city_norm) as city_norm,
                COALESCE(w.lob_base, m.lob_base) as lob_base,
                COALESCE(w.segment, m.segment) as segment,
                COALESCE(w.trips_plan_week_sum, 0) as trips_plan_week_sum,
                COALESCE(m.trips_plan_month, 0) as trips_plan_month,
                COALESCE(w.drivers_plan_week_sum, 0) as drivers_plan_week_sum,
                COALESCE(m.drivers_plan_month, 0) as drivers_plan_month,
                COALESCE(w.revenue_plan_week_sum, 0) as revenue_plan_week_sum,
                COALESCE(m.revenue_plan_month, 0) as revenue_plan_month,
                ABS(COALESCE(w.trips_plan_week_sum, 0) - COALESCE(m.trips_plan_month, 0)) as diff_trips,
                ABS(COALESCE(w.drivers_plan_week_sum, 0) - COALESCE(m.drivers_plan_month, 0)) as diff_drivers,
                ABS(COALESCE(w.revenue_plan_week_sum, 0) - COALESCE(m.revenue_plan_month, 0)) as diff_revenue
            FROM plan_weekly w
            FULL OUTER JOIN plan_monthly m
              ON w.month = m.month
             AND w.country = m.country
             AND w.city_norm = m.city_norm
             AND w.lob_base = m.lob_base
             AND w.segment = m.segment
            ORDER BY diff_trips DESC, diff_drivers DESC, diff_revenue DESC
            LIMIT 20;
        """)
        rows = cursor.fetchall()
        has_diff = False
        for row in rows:
            if row['diff_trips'] > 0.01 or row['diff_drivers'] > 0.01 or row['diff_revenue'] > 0.01:
                has_diff = True
                print(f"\n  {row['month']} | {row['country']} | {row['city_norm']} | {row['lob_base']} | {row['segment']}")
                print(f"    trips_week={row['trips_plan_week_sum']} vs trips_month={row['trips_plan_month']} (diff={row['diff_trips']})")
                print(f"    drivers_week={row['drivers_plan_week_sum']} vs drivers_month={row['drivers_plan_month']} (diff={row['diff_drivers']})")
                print(f"    revenue_week={row['revenue_plan_week_sum']} vs revenue_month={row['revenue_plan_month']} (diff={row['diff_revenue']})")
        if not has_diff:
            print("\n  [OK] Sumas semanales igualan al plan mensual (tolerancia 0.01)")
        return not has_diff
    finally:
        cursor.close()


def main():
    from sqlalchemy import create_engine

    print("=" * 80)
    print("VALIDACION FASE 2B - SEMANAL")
    print("=" * 80)

    url = _get_database_url()
    if not url or url.startswith("driver://"):
        logger.error("DATABASE_URL no configurada o invalida")
        return 1

    engine = create_engine(
        url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as conn:
            raw_conn = conn.connection
            # Timeout para queries largas (reconciliacion, plan sum)
            cur = raw_conn.cursor()
            try:
                cur.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'")
                logger.info("statement_timeout configurado: %s", STATEMENT_TIMEOUT)
            finally:
                cur.close()

            cur = raw_conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_matviews
                        WHERE schemaname = 'ops'
                          AND matviewname = 'mv_real_trips_weekly'
                    ) as exists;
                """)
                mv_exists = cur.fetchone()['exists']
            finally:
                cur.close()

            if not mv_exists:
                print("\n[ERROR] MV semanal no existe. Ejecuta la migracion 014 primero.")
                return 1

            validations = [
                ("Unicidad", validate_uniqueness),
                ("Reconciliacion", validate_reconciliation),
                ("Sanity", validate_sanity),
                ("PlanSum", validate_plan_weekly_sum),
            ]
            results = []
            for name, fn in validations:
                try:
                    passed = fn(raw_conn)
                    results.append((name, passed))
                except Exception as e:
                    if _is_timeout_error(e):
                        logger.error("[FAIL] Timeout en validacion %s: %s", name, e)
                        print(f"\n  [FAIL] Reconciliacion/validacion: statement timeout - {e}")
                    else:
                        logger.exception("Error en validacion %s", name)
                        raise
                    results.append((name, False))

            print("\n" + "=" * 80)
            print("RESUMEN DE VALIDACIONES")
            print("=" * 80)

            all_passed = True
            for name, passed in results:
                status = "[OK]" if passed else "[FAIL]"
                print(f"  {name}: {status}")
                if not passed and name in ["Unicidad", "Reconciliacion", "PlanSum"]:
                    all_passed = False

            if all_passed:
                print("\n[OK] Validaciones criticas pasaron")
                return 0
            print("\n[ERROR] Validaciones criticas fallaron")
            return 1
    except Exception as e:
        logger.error("Error general: %s", e)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
