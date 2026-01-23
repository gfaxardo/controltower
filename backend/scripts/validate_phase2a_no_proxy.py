#!/usr/bin/env python3
"""
Script de validación para Fase 2A: Eliminación de proxies y uso de revenue real.
Valida cobertura, reconciliación, unicidad y sanity checks.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_commission_coverage(conn):
    """3.1: Validar cobertura de comisión (últimos 3 meses)"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("3.1 VALIDACION: Cobertura de Comision (ultimos 3 meses)")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            COALESCE(dp.country, '') as country,
            COUNT(*) FILTER (WHERE NULLIF(t.comision_empresa_asociada, 0) IS NOT NULL) AS trips_with_commission,
            COUNT(*) AS trips_total,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE NULLIF(t.comision_empresa_asociada, 0) IS NOT NULL) / NULLIF(COUNT(*), 0),
                2
            ) AS pct_coverage
        FROM public.trips_all t
        LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
        WHERE t.condicion = 'Completado'
          AND t.fecha_inicio_viaje >= DATE_TRUNC('month', NOW()) - INTERVAL '3 months'
          AND t.fecha_inicio_viaje < DATE_TRUNC('month', NOW())
        GROUP BY COALESCE(dp.country, '')
        ORDER BY COALESCE(dp.country, '');
    """)
    
    results = cursor.fetchall()
    all_ok = True
    
    for row in results:
        country = row['country'] or 'NULL'
        pct = row['pct_coverage'] or 0
        trips_with = row['trips_with_commission'] or 0
        trips_total = row['trips_total'] or 0
        
        print(f"\n  Pais: {country}")
        print(f"  Viajes con comision: {trips_with:,} / {trips_total:,}")
        print(f"  Cobertura: {pct:.2f}%")
        
        if pct < 95.0:
            print(f"  [WARNING] Cobertura < 95% en {country}")
            all_ok = False
            
            # Mostrar ejemplos de viajes sin comisión
            cursor.execute("""
                SELECT 
                    t.fecha_inicio_viaje,
                    t.park_id,
                    t.tipo_servicio,
                    t.precio_yango_pro,
                    t.comision_empresa_asociada
                FROM public.trips_all t
                LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
                WHERE t.condicion = 'Completado'
                  AND t.fecha_inicio_viaje >= DATE_TRUNC('month', NOW()) - INTERVAL '3 months'
                  AND (t.comision_empresa_asociada IS NULL OR t.comision_empresa_asociada = 0)
                  AND (COALESCE(dp.country, '') = %s OR (%s = '' AND COALESCE(dp.country, '') = ''))
                ORDER BY t.fecha_inicio_viaje DESC
                LIMIT 5;
            """, (country if country != 'NULL' else '', country if country != 'NULL' else ''))
            
            examples = cursor.fetchall()
            if examples:
                print(f"  Ejemplos de viajes sin comision (top 5):")
                for ex in examples:
                    print(f"    - {ex['fecha_inicio_viaje']} | park={ex['park_id']} | precio={ex['precio_yango_pro']} | comision={ex['comision_empresa_asociada']}")
        else:
            print(f"  [OK] Cobertura >= 95%")
    
    if all_ok:
        print("\n  [OK] Todos los paises tienen cobertura >= 95%")
    else:
        print("\n  [WARNING] Algunos paises tienen cobertura < 95% (no bloquea)")
    
    cursor.close()
    return all_ok

def validate_reconciliation(conn):
    """3.2: Reconciliación mensual (mes último cerrado, por país)"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("3.2 VALIDACION: Reconciliacion Mensual (ultimo mes cerrado)")
    print("=" * 80)
    
    # Obtener último mes cerrado (mes anterior al actual)
    cursor.execute("""
        SELECT DATE_TRUNC('month', NOW() - INTERVAL '1 month')::DATE as last_closed_month;
    """)
    last_month = cursor.fetchone()['last_closed_month']
    
    print(f"\n  Mes a reconciliar: {last_month}")
    
    cursor.execute("""
        WITH direct_sum AS (
            SELECT 
                COALESCE(dp.country, '') as country,
                SUM(NULLIF(t.comision_empresa_asociada, 0)) as direct_revenue
            FROM public.trips_all t
            LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
            WHERE t.condicion = 'Completado'
              AND DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE = %s
            GROUP BY COALESCE(dp.country, '')
        ),
        mv_sum AS (
            SELECT 
                country,
                SUM(commission_yego_signed) as mv_commission_signed,
                SUM(revenue_real_yego) as mv_revenue
            FROM ops.mv_real_trips_monthly
            WHERE month = %s
            GROUP BY country
        )
        SELECT 
            COALESCE(d.country, m.country, 'NULL') as country,
            COALESCE(d.direct_revenue, 0) as direct_revenue,
            COALESCE(m.mv_commission_signed, 0) as mv_commission_signed,
            COALESCE(m.mv_revenue, 0) as mv_revenue,
            ABS(COALESCE(d.direct_revenue, 0) - COALESCE(m.mv_commission_signed, 0)) as diff_signed,
            ABS(COALESCE(m.mv_revenue, 0) + COALESCE(m.mv_commission_signed, 0)) as diff_sign
        FROM direct_sum d
        FULL OUTER JOIN mv_sum m ON d.country = m.country
        ORDER BY country;
    """, (last_month, last_month))
    
    results = cursor.fetchall()
    all_ok = True
    
    for row in results:
        country = row['country']
        direct = row['direct_revenue'] or 0
        mv_signed = row['mv_commission_signed'] or 0
        mv = row['mv_revenue'] or 0
        diff_signed = row['diff_signed'] or 0
        diff_sign = row['diff_sign'] or 0
        
        print(f"\n  Pais: {country}")
        print(f"  Direct (trips_all): {direct:,.2f}")
        print(f"  MV commission_yego_signed: {mv_signed:,.2f}")
        print(f"  MV revenue_real_yego: {mv:,.2f}")
        print(f"  Diff signed (direct vs signed): {diff_signed:,.2f}")
        print(f"  Diff sign (revenue + signed): {diff_sign:,.2f}")
        
        if diff_signed > 0.01:
            print(f"  [ERROR] Direct != commission_yego_signed en {country}")
            all_ok = False
        else:
            print(f"  [OK] Direct == commission_yego_signed")

        if diff_sign > 0.01:
            print(f"  [ERROR] revenue_real_yego != -commission_yego_signed en {country}")
            all_ok = False
        else:
            print(f"  [OK] revenue_real_yego == -commission_yego_signed")
    
    if all_ok:
        print("\n  [OK] Reconciliacion exitosa para todos los paises")
    else:
        print("\n  [ERROR] Reconciliacion fallida (bloquea)")
    
    cursor.close()
    return all_ok

def validate_uniqueness(conn):
    """3.3: Validar unicidad de MV v2"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("3.3 VALIDACION: Unicidad MV v2")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            month,
            country,
            city_norm,
            lob_base,
            segment,
            COUNT(*) as duplicate_count
        FROM ops.mv_real_trips_monthly
        GROUP BY month, country, city_norm, lob_base, segment
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, month DESC
        LIMIT 20;
    """)
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"\n  [ERROR] Encontrados {len(duplicates)} grupos con duplicados:")
        for dup in duplicates:
            print(f"    - {dup['month']} | {dup['country']} | {dup['city_norm']} | {dup['lob_base']} | {dup['segment']} ({dup['duplicate_count']} veces)")
        cursor.close()
        return False
    else:
        print("\n  [OK] No hay duplicados. Unicidad garantizada.")
        cursor.close()
        return True

def validate_sanity(conn):
    """3.4: Sanity checks"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("3.4 VALIDACION: Sanity Checks")
    print("=" * 80)
    
    all_ok = True
    
    # Check 1: revenue_real_yego no debe ser NULL (puede ser 0)
    cursor.execute("""
        SELECT COUNT(*) as null_revenue_count
        FROM ops.mv_real_trips_monthly
        WHERE revenue_real_yego IS NULL;
    """)
    null_revenue = cursor.fetchone()['null_revenue_count']
    
    print(f"\n  Check 1: revenue_real_yego NULL")
    print(f"    Filas con revenue NULL: {null_revenue}")
    if null_revenue > 0:
        print(f"    [ERROR] revenue_real_yego no debe ser NULL")
        all_ok = False
    else:
        print(f"    [OK] No hay revenue NULL")
    
    # Check 2: trips_real_completed > 0 en meses con data
    cursor.execute("""
        SELECT COUNT(*) as zero_trips_count
        FROM ops.mv_real_trips_monthly
        WHERE trips_real_completed = 0
          AND revenue_real_yego > 0;
    """)
    zero_trips = cursor.fetchone()['zero_trips_count']
    
    print(f"\n  Check 2: trips_real_completed > 0 cuando hay revenue")
    print(f"    Filas con trips=0 pero revenue>0: {zero_trips}")
    if zero_trips > 0:
        print(f"    [WARNING] Inconsistencia: revenue sin trips (revisar)")
        # No bloquea, solo warning
    else:
        print(f"    [OK] Consistencia trips/revenue")
    
    # Check 3: is_partial_real solo en mes actual
    cursor.execute("SELECT DATE_TRUNC('month', NOW())::DATE as current_month")
    current_month = cursor.fetchone()['current_month']
    
    cursor.execute("""
        SELECT 
            month,
            COUNT(*) FILTER (WHERE is_partial_real = true) as partial_count,
            COUNT(*) FILTER (WHERE is_partial_real = false) as complete_count
        FROM ops.mv_real_trips_monthly
        WHERE month >= DATE_TRUNC('month', NOW())::DATE - INTERVAL '2 months'
        GROUP BY month
        ORDER BY month DESC;
    """)
    
    partial_check = cursor.fetchall()
    print(f"\n  Check 3: is_partial_real solo en mes actual")
    for row in partial_check:
        month = row['month']
        partial = row['partial_count'] or 0
        complete = row['complete_count'] or 0
        is_current = (month == current_month)
        
        if is_current:
            if partial > 0:
                print(f"    {month}: {partial} parcial, {complete} completo [OK]")
            else:
                print(f"    {month}: Sin parciales [WARNING]")
        else:
            if complete > 0 and partial == 0:
                print(f"    {month}: {complete} completo [OK]")
            else:
                print(f"    {month}: {partial} parcial, {complete} completo [WARNING]")
    
    cursor.close()
    return all_ok

def validate_margen_unitario(conn):
    """Validar margen_unitario_yego"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    print("\n" + "=" * 80)
    print("VALIDACION: Margen Unitario YEGO")
    print("=" * 80)

    all_ok = True

    # Check 1: margen_unitario_yego IS NULL solo cuando trips_real_completed = 0
    cursor.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE margen_unitario_yego IS NULL AND trips_real_completed > 0) as invalid_null,
            COUNT(*) FILTER (WHERE margen_unitario_yego IS NOT NULL AND trips_real_completed = 0) as invalid_not_null
        FROM ops.mv_real_trips_monthly;
    """)
    row = cursor.fetchone()
    invalid_null = row['invalid_null'] or 0
    invalid_not_null = row['invalid_not_null'] or 0

    print(f"\n  Check 1: margen_unitario_yego NULL solo si trips=0")
    print(f"    NULL con trips>0: {invalid_null}")
    print(f"    NOT NULL con trips=0: {invalid_not_null}")
    if invalid_null > 0 or invalid_not_null > 0:
        print("    [ERROR] Inconsistencia en margen_unitario_yego")
        all_ok = False
    else:
        print("    [OK] Consistencia margen/trips")

    # Check 2: margen_unitario_yego >= 0
    cursor.execute("""
        SELECT COUNT(*) as negative_count
        FROM ops.mv_real_trips_monthly
        WHERE margen_unitario_yego < 0;
    """)
    negative_count = cursor.fetchone()['negative_count'] or 0
    print(f"\n  Check 2: margen_unitario_yego >= 0")
    print(f"    Filas con margen negativo: {negative_count}")
    if negative_count > 0:
        print("    [ERROR] Margen negativo encontrado")
        all_ok = False
    else:
        print("    [OK] Margen no negativo")

    # Sample por país (último mes cerrado)
    cursor.execute("SELECT DATE_TRUNC('month', NOW() - INTERVAL '1 month')::DATE as last_closed_month;")
    last_month = cursor.fetchone()['last_closed_month']
    print(f"\n  Sample último mes cerrado: {last_month}")

    cursor.execute("""
        SELECT 
            country,
            SUM(revenue_real_yego) as revenue_real_yego,
            SUM(trips_real_completed) as trips_real_completed,
            CASE 
                WHEN SUM(trips_real_completed) > 0 
                THEN SUM(revenue_real_yego) / SUM(trips_real_completed)
                ELSE NULL
            END as margen_unitario_yego
        FROM ops.mv_real_trips_monthly
        WHERE month = %s
        GROUP BY country
        ORDER BY country;
    """, (last_month,))
    rows = cursor.fetchall()
    for r in rows:
        if r['margen_unitario_yego'] is not None:
            print(f"    {r['country']}: revenue={r['revenue_real_yego']:.2f}, trips={r['trips_real_completed']}, margen={r['margen_unitario_yego']:.4f}")
        else:
            print(f"    {r['country']}: revenue={r['revenue_real_yego']:.2f}, trips={r['trips_real_completed']}, margen=NULL")

    cursor.close()
    return all_ok

def main():
    print("=" * 80)
    print("VALIDACION FASE 2A: ELIMINACION DE PROXIES")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            # Verificar que MV v2 existe
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews 
                    WHERE schemaname = 'ops' 
                    AND matviewname = 'mv_real_trips_monthly'
                ) as exists;
            """)
            mv_exists = cursor.fetchone()['exists']
            cursor.close()
            
            if not mv_exists:
                print("\n[ERROR] MV v2 no existe. Ejecuta la migracion 013 primero.")
                return 1
            
            # Ejecutar validaciones
            results = []
            
            results.append(("Cobertura", validate_commission_coverage(conn)))
            results.append(("Reconciliacion", validate_reconciliation(conn)))
            results.append(("Unicidad", validate_uniqueness(conn)))
            results.append(("Sanity", validate_sanity(conn)))
            results.append(("MargenUnitario", validate_margen_unitario(conn)))
            
            # Resumen final
            print("\n" + "=" * 80)
            print("RESUMEN DE VALIDACIONES")
            print("=" * 80)
            
            all_passed = True
            for name, passed in results:
                status = "[OK]" if passed else "[FAIL]"
                print(f"  {name}: {status}")
                if not passed and name in ["Reconciliacion", "Unicidad", "MargenUnitario"]:
                    all_passed = False
            
            if all_passed:
                print("\n[OK] Todas las validaciones criticas pasaron")
                print("MV v2 esta lista para swap.")
                return 0
            else:
                print("\n[ERROR] Algunas validaciones criticas fallaron")
                print("No proceder con swap hasta resolver los errores.")
                return 1
                
    except Exception as e:
        logger.error(f"Error general: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
