"""
PASO 5: Validación con números
Confirma que revenue_yego_real es razonable y mucho menor que gmv_total
"""

import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

print("=" * 70)
print("PASO 5 - VALIDACION CON NUMEROS")
print("=" * 70)

query = """
SELECT
  country, 
  EXTRACT(YEAR FROM month)::int AS year, 
  EXTRACT(MONTH FROM month)::int AS month,
  SUM(gmv_passenger_paid) AS gmv_base,
  SUM(gmv_total) AS gmv_total,
  SUM(revenue_yego_real) AS yego_rev,
  SUM(revenue_yango_real) AS yango_rev,
  ROUND(SUM(revenue_yego_real)/NULLIF(SUM(gmv_passenger_paid),0),4) AS take_rate_yego,
  ROUND((SUM(revenue_yego_real)+SUM(revenue_yango_real))/NULLIF(SUM(gmv_passenger_paid),0),4) AS take_rate_total,
  SUM(trips_real_completed) AS trips
FROM ops.mv_real_trips_monthly
WHERE EXTRACT(YEAR FROM month) = 2025
GROUP BY 1,2,3
ORDER BY 1,2,3
LIMIT 24;
"""

with get_db() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    
    print("\nVALIDACION - Real 2025 (primeros 24 meses/países):")
    print("-" * 70)
    print(f"{'País':<6} {'Año':<4} {'Mes':<4} {'GMV Base':<15} {'GMV Total':<15} {'Rev YEGO':<15} {'Take YEGO':<10} {'Trips':<12}")
    print("-" * 70)
    
    for row in results:
        print(f"{row['country']:<6} {row['year']:<4} {row['month']:<4} "
              f"{row['gmv_base']:>14,.0f} {row['gmv_total']:>14,.0f} "
              f"{row['yego_rev']:>14,.0f} {row['take_rate_yego']:>9.4f} "
              f"{row['trips']:>11,}")
    
    # Estadísticas agregadas
    print("\n" + "=" * 70)
    print("ESTADISTICAS AGREGADAS (2025):")
    print("=" * 70)
    
    stats_query = """
    SELECT
      COUNT(*) AS n_periods,
      SUM(gmv_passenger_paid) AS total_gmv_base,
      SUM(revenue_yego_real) AS total_yego_rev,
      AVG(take_rate_yego) AS avg_take_rate_yego,
      MIN(take_rate_yego) AS min_take_rate_yego,
      MAX(take_rate_yego) AS max_take_rate_yego
    FROM ops.mv_real_trips_monthly
    WHERE EXTRACT(YEAR FROM month) = 2025
    AND take_rate_yego IS NOT NULL;
    """
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(stats_query)
    stats = cursor.fetchone()
    cursor.close()
    
    if stats and stats['n_periods']:
        print(f"  Períodos con take_rate: {stats['n_periods']}")
        print(f"  GMV Base total: {stats['total_gmv_base']:,.0f}")
        print(f"  Revenue YEGO total: {stats['total_yego_rev']:,.0f}")
        print(f"  Ratio Revenue/GMV: {stats['total_yego_rev']/stats['total_gmv_base']*100:.2f}%")
        print(f"  Take rate YEGO promedio: {stats['avg_take_rate_yego']:.4f}")
        print(f"  Take rate YEGO rango: {stats['min_take_rate_yego']:.4f} - {stats['max_take_rate_yego']:.4f}")
        
        # Validación
        print("\n" + "=" * 70)
        print("VALIDACION:")
        print("=" * 70)
        
        if stats['total_yego_rev'] < stats['total_gmv_base']:
            print("  [OK] Revenue YEGO < GMV Base (CORRECTO)")
        else:
            print("  [ERROR] Revenue YEGO >= GMV Base (INCORRECTO)")
        
        if 0.01 <= stats['avg_take_rate_yego'] <= 0.50:
            print(f"  [OK] Take rate YEGO razonable ({stats['avg_take_rate_yego']:.4f})")
        else:
            print(f"  [WARN] Take rate YEGO fuera de rango esperado ({stats['avg_take_rate_yego']:.4f})")
    else:
        print("  [WARN] No se encontraron datos para validar")
