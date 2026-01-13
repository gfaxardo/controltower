#!/usr/bin/env python3
"""
Script de exploración para mapear líneas de negocio desde trips_all.
trips_all es la FUENTE PRINCIPAL de ejecución (trips y revenue).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor
import json
from collections import defaultdict

def explorar_estructura_trips_all():
    """Explora la estructura de trips_all y campos clave"""
    print("\n" + "="*80)
    print("1. ESTRUCTURA DE trips_all (Fuente Principal de Ejecución)")
    print("="*80)
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT 
                    COUNT(*) as total_trips,
                    COUNT(DISTINCT park_id) as parks_distintos,
                    COUNT(DISTINCT driver_id) as drivers_distintos,
                    COUNT(CASE WHEN park_id IS NOT NULL THEN 1 END) as trips_con_park_id,
                    COUNT(CASE WHEN driver_id IS NOT NULL THEN 1 END) as trips_con_driver_id,
                    COUNT(CASE WHEN tipo_servicio IS NOT NULL THEN 1 END) as trips_con_tipo_servicio
                FROM public.trips_all
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            query_cols = """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' 
                AND table_name = 'trips_all'
                ORDER BY ordinal_position
            """
            cursor.execute(query_cols)
            columns = cursor.fetchall()
            
            cursor.close()
            
            if result:
                print(f"\nESTADISTICAS GENERALES:")
                print(f"  Total de viajes: {result['total_trips']:,}")
                print(f"  Parks distintos: {result['parks_distintos']:,}")
                print(f"  Drivers distintos: {result['drivers_distintos']:,}")
                print(f"\nCOBERTURA DE CAMPOS CLAVE:")
                total = result['total_trips']
                if total > 0:
                    print(f"  Viajes con park_id: {result['trips_con_park_id']:,} ({result['trips_con_park_id']/total*100:.1f}%)")
                    print(f"  Viajes con driver_id: {result['trips_con_driver_id']:,} ({result['trips_con_driver_id']/total*100:.1f}%)")
                    print(f"  Viajes con tipo_servicio: {result['trips_con_tipo_servicio']:,} ({result['trips_con_tipo_servicio']/total*100:.1f}%)")
                
                revenue_cols = [c for c in columns if any(term in c['column_name'].lower() for term in ['revenue', 'ingreso', 'income', 'amount', 'money', 'precio', 'price', 'total'])]
                
                if revenue_cols:
                    print(f"\n  Campos de revenue detectados:")
                    for col in revenue_cols:
                        print(f"    - {col['column_name']} ({col['data_type']})")
                
                return dict(result)
            else:
                print("\nADVERTENCIA: No se encontraron datos")
                return {}
                
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return {}

def explorar_tipo_servicio_en_trips():
    """Explora valores únicos de tipo_servicio en trips_all"""
    print("\n" + "="*80)
    print("2. VALORES DE tipo_servicio EN trips_all")
    print("="*80)
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT 
                    tipo_servicio,
                    COUNT(*) as total_trips,
                    COUNT(DISTINCT park_id) as parks_distintos
                FROM public.trips_all
                WHERE tipo_servicio IS NOT NULL
                GROUP BY tipo_servicio
                ORDER BY total_trips DESC
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            if results:
                total_con_tipo = sum(r['total_trips'] for r in results)
                print(f"\nTotal de valores únicos: {len(results)}")
                print(f"Total de viajes con tipo_servicio: {total_con_tipo:,}\n")
                print(f"{'tipo_servicio':<40} {'Total Trips':<15} {'Parks':<10} {'% del total'}")
                print("-" * 75)
                
                valores = []
                for row in results:
                    pct = (row['total_trips'] / total_con_tipo * 100) if total_con_tipo > 0 else 0
                    print(f"{str(row['tipo_servicio']):<40} {row['total_trips']:<15,} {row['parks_distintos']:<10} {pct:.1f}%")
                    valores.append({
                        'valor': str(row['tipo_servicio']),
                        'trips': row['total_trips'],
                        'pct': pct
                    })
                
                return valores
            else:
                print("\nADVERTENCIA: No se encontraron valores de tipo_servicio")
                return []
                
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return []

def comparar_tipo_servicio_vs_default_lob():
    """Compara tipo_servicio con default_line_of_business del park"""
    print("\n" + "="*80)
    print("3. COMPARACIÓN: tipo_servicio vs default_line_of_business")
    print("="*80)
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT 
                    COALESCE(t.tipo_servicio, 'NULL') as tipo_servicio,
                    COALESCE(d.default_line_of_business, 'NULL') as default_line_of_business,
                    COUNT(*) as total_trips
                FROM public.trips_all t
                LEFT JOIN dim.dim_park d ON t.park_id = d.park_id
                WHERE t.tipo_servicio IS NOT NULL
                GROUP BY t.tipo_servicio, d.default_line_of_business
                ORDER BY total_trips DESC
                LIMIT 50
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            if results:
                print(f"\nTotal de combinaciones: {len(results)}\n")
                print(f"{'tipo_servicio':<30} {'default_line_of_business':<25} {'Total Trips':<15}")
                print("-" * 70)
                
                for row in results:
                    tipo_serv = str(row['tipo_servicio'])[:28]
                    default_lob = str(row['default_line_of_business'])[:23]
                    print(f"{tipo_serv:<30} {default_lob:<25} {row['total_trips']:<15,}")
                
                return [dict(row) for row in results]
            else:
                print("\nADVERTENCIA: No se encontraron combinaciones")
                return []
                
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return []

def explorar_work_term():
    """Explora work_term en drivers"""
    print("\n" + "="*80)
    print("4. VALORES DE work_term EN drivers")
    print("="*80)
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT 
                    work_term,
                    COUNT(DISTINCT driver_id) as total_drivers,
                    COUNT(DISTINCT park_id) as parks_distintos
                FROM public.drivers
                WHERE work_term IS NOT NULL
                GROUP BY work_term
                ORDER BY total_drivers DESC
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            if results:
                print(f"\nTotal de valores únicos: {len(results)}\n")
                print(f"{'work_term':<40} {'Total Drivers':<20} {'Parks':<10}")
                print("-" * 70)
                
                valores = []
                for row in results:
                    print(f"{str(row['work_term']):<40} {row['total_drivers']:<20,} {row['parks_distintos']:<10}")
                    valores.append({
                        'valor': str(row['work_term']),
                        'drivers': row['total_drivers']
                    })
                
                return valores
            else:
                print("\nADVERTENCIA: No se encontraron valores de work_term")
                return []
                
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return []

def obtener_lineas_negocio_requeridas():
    """Muestra las líneas de negocio requeridas"""
    print("\n" + "="*80)
    print("5. LÍNEAS DE NEGOCIO REQUERIDAS")
    print("="*80)
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT DISTINCT 
                    COALESCE(d.default_line_of_business, '') as line_of_business,
                    COUNT(DISTINCT d.park_id) as park_count
                FROM bi.real_monthly_agg r
                LEFT JOIN dim.dim_park d ON r.park_id = d.park_id
                WHERE r.year = 2025
                AND COALESCE(r.orders_completed, 0) > 0
                AND COALESCE(d.default_line_of_business, '') != ''
                GROUP BY d.default_line_of_business
                ORDER BY line_of_business
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            if results:
                print(f"\nLíneas de negocio actuales en universo ({len(results)}):\n")
                for row in results:
                    print(f"  - {row['line_of_business']} ({row['park_count']} parks)")
                
                return [dict(row) for row in results]
            else:
                print("\nADVERTENCIA: No se encontraron líneas de negocio")
                return []
                
    except Exception as e:
        print(f"\nERROR: {e}")
        return []

def generar_sugerencia_mapeo(tipo_servicio_valores, lineas_requeridas):
    """Genera sugerencias de mapeo basado en los valores encontrados"""
    print("\n" + "="*80)
    print("6. SUGERENCIA DE MAPEO tipo_servicio → línea de negocio")
    print("="*80)
    
    lineas = [l['line_of_business'] for l in lineas_requeridas]
    
    print("\nMAPEO SUGERIDO (ajustar segun valores reales):\n")
    print("TIPO_SERVICIO_MAPPING = {")
    
    mapeos_sugeridos = {}
    for valor in tipo_servicio_valores:
        val_lower = valor['valor'].lower().strip()
        
        sugerencia = None
        if any(term in val_lower for term in ['taxi', 'auto', 'car', 'coche']):
            sugerencia = 'Auto Taxi'
        elif any(term in val_lower for term in ['delivery', 'entrega', 'envio']):
            sugerencia = 'Delivery'
        elif any(term in val_lower for term in ['moto', 'motorcycle', 'motocicleta']):
            sugerencia = 'Moto'
        
        if sugerencia:
            mapeos_sugeridos[val_lower] = sugerencia
            print(f"    '{val_lower}': '{sugerencia}',  # {valor['trips']:,} trips ({valor['pct']:.1f}%)")
    
    print("}")
    
    return mapeos_sugeridos

def main():
    """Función principal"""
    print("\n" + "="*80)
    print("EXPLORACIÓN DE MAPEO DE LÍNEAS DE NEGOCIO")
    print("="*80)
    
    try:
        init_db_pool()
        print("\nConexion establecida\n")
        
        estructura = explorar_estructura_trips_all()
        tipo_servicio_valores = explorar_tipo_servicio_en_trips()
        comparacion = comparar_tipo_servicio_vs_default_lob()
        work_term_valores = explorar_work_term()
        lineas_requeridas = obtener_lineas_negocio_requeridas()
        
        if tipo_servicio_valores and lineas_requeridas:
            generar_sugerencia_mapeo(tipo_servicio_valores, lineas_requeridas)
        
        print("\n" + "="*80)
        print("Exploracion completada")
        print("="*80)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
