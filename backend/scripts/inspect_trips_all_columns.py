"""
Script para inspeccionar las columnas reales de trips_all.
Detecta nombres exactos de columnas para trip_id, trip_date, tipo_servicio, etc.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_trips_all():
    """Inspecciona la estructura de trips_all."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            # Obtener todas las columnas
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'trips_all'
                ORDER BY ordinal_position
            """)
            
            columns = cursor.fetchall()
            
            print("\n" + "=" * 60)
            print("ESTRUCTURA DE trips_all")
            print("=" * 60)
            print(f"\nTotal de columnas: {len(columns)}\n")
            
            # Buscar columnas relevantes
            relevant = {
                'trip_id': None,
                'trip_date': None,
                'country': None,
                'city': None,
                'tipo_servicio': None,
                'service_type': None,
                'pago_corporativo': None,
                'corporate_payment': None,
                'product_type': None,
                'vehicle_type': None,
                'fleet_flag': None,
                'tariff_class': None
            }
            
            print("Columnas encontradas:\n")
            for col_name, col_type, is_nullable in columns:
                col_lower = col_name.lower()
                
                # Mapear a campos relevantes
                if 'id' in col_lower and ('trip' in col_lower or col_lower == 'id'):
                    relevant['trip_id'] = col_name
                if 'fecha' in col_lower and 'inicio' in col_lower:
                    relevant['trip_date'] = col_name
                if col_lower == 'country':
                    relevant['country'] = col_name
                if col_lower == 'city':
                    relevant['city'] = col_name
                if 'tipo_servicio' in col_lower or col_lower == 'tipo_servicio':
                    relevant['tipo_servicio'] = col_name
                if 'service_type' in col_lower:
                    relevant['service_type'] = col_name
                if 'pago_corporativo' in col_lower:
                    relevant['pago_corporativo'] = col_name
                if 'corporate' in col_lower and 'payment' in col_lower:
                    relevant['corporate_payment'] = col_name
                if 'product_type' in col_lower:
                    relevant['product_type'] = col_name
                if 'vehicle_type' in col_lower:
                    relevant['vehicle_type'] = col_name
                if 'fleet' in col_lower and 'flag' in col_lower:
                    relevant['fleet_flag'] = col_name
                if 'tariff' in col_lower and 'class' in col_lower:
                    relevant['tariff_class'] = col_name
                
                print(f"  {col_name:30} {col_type:20} {'NULL' if is_nullable == 'YES' else 'NOT NULL'}")
            
            print("\n" + "=" * 60)
            print("COLUMNAS RELEVANTES DETECTADAS")
            print("=" * 60)
            for key, value in relevant.items():
                status = "OK" if value else "NO"
                print(f"{status:3} {key:20} -> {value or 'NO ENCONTRADA'}")
            
            # Verificar muestra de datos
            print("\n" + "=" * 60)
            print("MUESTRA DE DATOS (3 filas)")
            print("=" * 60)
            
            sample_cols = [c for c in [relevant['trip_id'], relevant['trip_date'], relevant['country'], 
                                      relevant['city'], relevant['tipo_servicio'], relevant['pago_corporativo']] if c]
            
            if sample_cols:
                cols_str = ', '.join(sample_cols)
                cursor.execute(f"SELECT {cols_str} FROM public.trips_all LIMIT 3")
                samples = cursor.fetchall()
                
                print(f"\nColumnas: {cols_str}\n")
                for i, row in enumerate(samples, 1):
                    print(f"Fila {i}:")
                    for col, val in zip(sample_cols, row):
                        print(f"  {col}: {val}")
                    print()
            
            return relevant
            
        except Exception as e:
            logger.error(f"Error al inspeccionar trips_all: {e}")
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    inspect_trips_all()
