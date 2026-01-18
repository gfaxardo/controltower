"""
Verificar nombres de columnas en trips_all para GMV y revenue
"""

import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

print("=" * 70)
print("VERIFICAR COLUMNAS EN trips_all PARA GMV Y REVENUE")
print("=" * 70)

query = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'trips_all'
AND (
  column_name ILIKE '%efectivo%'
  OR column_name ILIKE '%tarjeta%'
  OR column_name ILIKE '%pago_corporativo%'
  OR column_name ILIKE '%propina%'
  OR column_name ILIKE '%otros_pagos%'
  OR column_name ILIKE '%bonificaciones%'
  OR column_name ILIKE '%promocion%'
  OR column_name ILIKE '%comision%'
  OR column_name ILIKE '%precio%'
  OR column_name ILIKE '%fecha%'
  OR column_name ILIKE '%condicion%'
  OR column_name ILIKE '%status%'
)
ORDER BY column_name;
"""

with get_db() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query)
    columns = cursor.fetchall()
    cursor.close()
    
    print("\nCOLUMNAS RELEVANTES ENCONTRADAS:")
    for col in columns:
        print(f"  - {col['column_name']} ({col['data_type']})")
    
    # Buscar columnas específicas
    col_names = [c['column_name'] for c in columns]
    
    print("\n" + "=" * 70)
    print("MAPEO DE COLUMNAS:")
    print("=" * 70)
    
    # Identificar columnas de pago
    efectivo_col = next((c for c in col_names if 'efectivo' in c.lower()), None)
    tarjeta_col = next((c for c in col_names if 'tarjeta' in c.lower()), None)
    corporativo_col = next((c for c in col_names if 'pago_corporativo' in c.lower() or 'corporativo' in c.lower()), None)
    propina_col = next((c for c in col_names if 'propina' in c.lower()), None)
    
    # Identificar columnas de fecha/estado
    fecha_col = next((c for c in col_names if 'fecha' in c.lower() and 'inicio' in c.lower()), 'fecha_inicio_viaje')
    condicion_col = next((c for c in col_names if 'condicion' in c.lower()), 'condicion')
    
    # Identificar comisiones
    comision_yego_col = next((c for c in col_names if 'comision' in c.lower() and 'empresa' in c.lower()), 'comision_empresa_asociada')
    comision_yango_col = next((c for c in col_names if 'comision' in c.lower() and 'servicio' in c.lower()), 'comision_servicio')
    
    print(f"\n  GMV Base (passenger_paid):")
    print(f"    efectivo: {efectivo_col or 'NO ENCONTRADO'}")
    print(f"    tarjeta: {tarjeta_col or 'NO ENCONTRADO'}")
    print(f"    pago_corporativo: {corporativo_col or 'NO ENCONTRADO'}")
    
    print(f"\n  Extras:")
    print(f"    propina: {propina_col or 'NO ENCONTRADO'}")
    
    print(f"\n  Revenue:")
    print(f"    comision_empresa_asociada: {comision_yego_col}")
    print(f"    comision_servicio: {comision_yango_col}")
    
    print(f"\n  Filtros:")
    print(f"    fecha_inicio_viaje: {fecha_col}")
    print(f"    condicion: {condicion_col}")
