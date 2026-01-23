#!/usr/bin/env python3
"""
Validaciones Fase 2B (semanal):
- Unicidad MV semanal
- Reconciliacion semanal vs trips_all (ultima semana cerrada)
- Sanity (signos de revenue/commission)
- Plan semanal suma a plan mensual
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_uniqueness(conn):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
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
        cursor.close()
        return False
    print("\n  [OK] Unicidad garantizada (0 duplicados)")
    cursor.close()
    return True


def validate_reconciliation(conn):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
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
    cursor.close()
    return all_ok


def validate_sanity(conn):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
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

    cursor.close()
    return negative_revenue == 0


def validate_plan_weekly_sum(conn):
    cursor = conn.cursor(cursor_factory=RealDictCursor)
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
    cursor.close()
    return not has_diff


def main():
    print("=" * 80)
    print("VALIDACION FASE 2B - SEMANAL")
    print("=" * 80)

    init_db_pool()
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews
                    WHERE schemaname = 'ops'
                      AND matviewname = 'mv_real_trips_weekly'
                ) as exists;
            """)
            mv_exists = cursor.fetchone()['exists']
            cursor.close()

            if not mv_exists:
                print("\n[ERROR] MV semanal no existe. Ejecuta la migracion 014 primero.")
                return 1

            results = []
            results.append(("Unicidad", validate_uniqueness(conn)))
            results.append(("Reconciliacion", validate_reconciliation(conn)))
            results.append(("Sanity", validate_sanity(conn)))
            results.append(("PlanSum", validate_plan_weekly_sum(conn)))

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
        logger.error(f"Error general: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
