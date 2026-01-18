"""
PASO 1: Perfilar signos de comisiones
Verifica si comision_empresa_asociada y comision_servicio vienen negativas o positivas
"""

import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

print("=" * 70)
print("PASO 1 - PERFILAR SIGNOS DE COMISIONES")
print("=" * 70)

query = """
SELECT
  COUNT(*) AS n,
  SUM(CASE WHEN comision_empresa_asociada < 0 THEN 1 ELSE 0 END) AS n_neg_yego,
  SUM(CASE WHEN comision_empresa_asociada > 0 THEN 1 ELSE 0 END) AS n_pos_yego,
  MIN(comision_empresa_asociada) AS min_yego,
  MAX(comision_empresa_asociada) AS max_yego,
  SUM(CASE WHEN comision_servicio < 0 THEN 1 ELSE 0 END) AS n_neg_yango,
  SUM(CASE WHEN comision_servicio > 0 THEN 1 ELSE 0 END) AS n_pos_yango,
  MIN(comision_servicio) AS min_yango,
  MAX(comision_servicio) AS max_yango
FROM public.trips_all;
"""

with get_db() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    
    print("\nRESULTADOS:")
    print(f"  Total registros: {result['n']:,}")
    print(f"\n  COMISION_EMPRESA_ASOCIADA (YEGO):")
    print(f"    Negativas: {result['n_neg_yego']:,} ({result['n_neg_yego']/result['n']*100:.1f}%)")
    print(f"    Positivas: {result['n_pos_yego']:,} ({result['n_pos_yego']/result['n']*100:.1f}%)")
    print(f"    Min: {result['min_yego']}")
    print(f"    Max: {result['max_yego']}")
    
    print(f"\n  COMISION_SERVICIO (YANGO):")
    print(f"    Negativas: {result['n_neg_yango']:,} ({result['n_neg_yango']/result['n']*100:.1f}%)")
    print(f"    Positivas: {result['n_pos_yango']:,} ({result['n_pos_yango']/result['n']*100:.1f}%)")
    print(f"    Min: {result['min_yango']}")
    print(f"    Max: {result['max_yango']}")
    
    # Decisión de normalización
    print("\n" + "=" * 70)
    print("DECISION DE NORMALIZACION:")
    print("=" * 70)
    
    yego_mostly_neg = result['n_neg_yego'] > result['n_pos_yego']
    yango_mostly_neg = result['n_neg_yango'] > result['n_pos_yango']
    
    if yego_mostly_neg:
        print("  [YEGO] Mayormente NEGATIVAS -> Usar ABS()")
        revenue_yego_expr = "ABS(COALESCE(comision_empresa_asociada,0))"
    else:
        print("  [YEGO] Mayormente POSITIVAS -> Usar directo")
        revenue_yego_expr = "COALESCE(comision_empresa_asociada,0)"
    
    if yango_mostly_neg:
        print("  [YANGO] Mayormente NEGATIVAS -> Usar ABS()")
        revenue_yango_expr = "ABS(COALESCE(comision_servicio,0))"
    else:
        print("  [YANGO] Mayormente POSITIVAS -> Usar directo")
        revenue_yango_expr = "COALESCE(comision_servicio,0)"
    
    print(f"\n  EXPRESIONES FINALES:")
    print(f"    revenue_yego_trip = {revenue_yego_expr}")
    print(f"    revenue_yango_trip = {revenue_yango_expr}")
