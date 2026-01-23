#!/usr/bin/env python3
"""
Script para refrescar la vista materializada ops.mv_real_trips_monthly
con manejo de timeout y opciones de refresh.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def refresh_mv_concurrent(conn, timeout_seconds=3600):
    """
    Intenta refrescar la vista materializada de forma concurrente (no bloquea).
    Requiere índice único en la vista.
    """
    cursor = conn.cursor()
    try:
        # Establecer timeout para esta sesión
        cursor.execute(f"SET statement_timeout = '{timeout_seconds * 1000}ms'")
        logger.info(f"Timeout configurado a {timeout_seconds} segundos")
        
        logger.info("Iniciando REFRESH MATERIALIZED VIEW CONCURRENTLY...")
        start_time = time.time()
        
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_trips_monthly")
        conn.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"Refresh concurrente completado en {elapsed:.2f} segundos")
        return True, elapsed
        
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Refresh concurrente fallo: {error_msg}")
        if 'timeout' in error_msg.lower() or '57014' in error_msg:
            logger.warning("Timeout detectado. La vista puede ser muy grande o la consulta muy compleja.")
        elif 'unique index' in error_msg.lower() or 'concurrently' in error_msg.lower():
            logger.warning("Refresh concurrente requiere indice unico. Intentando refresh normal...")
        conn.rollback()
        return False, None

def refresh_mv_normal(conn, timeout_seconds=3600):
    """
    Refresca la vista materializada de forma normal (bloquea, pero es mas rapido).
    No requiere indice unico.
    """
    cursor = conn.cursor()
    try:
        # Establecer timeout para esta sesión
        cursor.execute(f"SET statement_timeout = '{timeout_seconds * 1000}ms'")
        logger.info(f"Timeout configurado a {timeout_seconds} segundos")
        
        logger.info("Iniciando REFRESH MATERIALIZED VIEW (normal, bloquea)...")
        logger.warning("NOTA: Este comando bloquea la vista durante el refresh")
        start_time = time.time()
        
        cursor.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly")
        conn.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"Refresh normal completado en {elapsed:.2f} segundos")
        return True, elapsed
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Refresh normal fallo: {error_msg}")
        if 'timeout' in error_msg.lower() or '57014' in error_msg:
            logger.error("Timeout detectado. Considera:")
            logger.error("1. Aumentar el timeout del servidor")
            logger.error("2. Verificar el tamaño de public.trips_all")
            logger.error("3. Optimizar la consulta de la vista materializada")
        conn.rollback()
        return False, None

def check_mv_status(conn):
    """Verifica el estado actual de la vista materializada"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verificar si existe y está poblada
        cursor.execute("""
            SELECT 
                schemaname,
                matviewname,
                hasindexes,
                ispopulated
            FROM pg_matviews 
            WHERE schemaname = 'ops' 
            AND matviewname = 'mv_real_trips_monthly';
        """)
        mv_info = cursor.fetchone()
        
        if mv_info:
            logger.info(f"Vista materializada: {mv_info['schemaname']}.{mv_info['matviewname']}")
            logger.info(f"  Tiene indices: {mv_info['hasindexes']}")
            logger.info(f"  Esta poblada: {mv_info['ispopulated']}")
        
        # Verificar tamaño de trips_all (tabla fuente)
        cursor.execute("""
            SELECT 
                pg_size_pretty(pg_total_relation_size('public.trips_all')) as size,
                reltuples::bigint as estimated_rows
            FROM pg_class
            WHERE relname = 'trips_all';
        """)
        trips_info = cursor.fetchone()
        if trips_info:
            logger.info(f"Tabla fuente (public.trips_all):")
            logger.info(f"  Tamaño: {trips_info['size']}")
            logger.info(f"  Filas estimadas: {trips_info['estimated_rows']:,}")
        
        # Verificar última actualización
        cursor.execute("SELECT MAX(refreshed_at) as last_refresh FROM ops.mv_real_trips_monthly")
        refresh_info = cursor.fetchone()
        if refresh_info and refresh_info['last_refresh']:
            logger.info(f"Ultima actualizacion: {refresh_info['last_refresh']}")
        
    except Exception as e:
        logger.warning(f"Error al verificar estado: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Refrescar vista materializada ops.mv_real_trips_monthly')
    parser.add_argument('--timeout', type=int, default=3600, 
                       help='Timeout en segundos (default: 3600 = 1 hora)')
    parser.add_argument('--method', choices=['concurrent', 'normal', 'auto'], default='auto',
                       help='Metodo de refresh: concurrent (no bloquea), normal (mas rapido), auto (intenta concurrent primero)')
    parser.add_argument('--check-only', action='store_true',
                       help='Solo verificar estado, no refrescar')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("REFRESH DE VISTA MATERIALIZADA: ops.mv_real_trips_monthly")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            # Verificar estado actual
            print("\n1. Estado actual de la vista:")
            check_mv_status(conn)
            
            if args.check_only:
                print("\n[Modo check-only: no se ejecutara refresh]")
                return 0
            
            # Ejecutar refresh según método
            print(f"\n2. Ejecutando refresh (metodo: {args.method}, timeout: {args.timeout}s)...")
            
            success = False
            elapsed = None
            
            if args.method == 'concurrent':
                success, elapsed = refresh_mv_concurrent(conn, args.timeout)
            elif args.method == 'normal':
                success, elapsed = refresh_mv_normal(conn, args.timeout)
            else:  # auto
                # Intentar concurrent primero
                success, elapsed = refresh_mv_concurrent(conn, args.timeout)
                if not success:
                    print("\nIntentando refresh normal como alternativa...")
                    success, elapsed = refresh_mv_normal(conn, args.timeout)
            
            if success:
                print("\n" + "=" * 80)
                print("REFRESH COMPLETADO EXITOSAMENTE")
                print("=" * 80)
                print(f"Tiempo transcurrido: {elapsed:.2f} segundos")
                
                # Verificar nueva fecha de actualización
                print("\n3. Verificando nueva fecha de actualizacion...")
                check_mv_status(conn)
                return 0
            else:
                print("\n" + "=" * 80)
                print("REFRESH FALLO")
                print("=" * 80)
                print("\nRecomendaciones:")
                print("1. Aumentar el timeout: --timeout 7200 (2 horas)")
                print("2. Verificar el tamaño de public.trips_all")
                print("3. Verificar logs del servidor PostgreSQL")
                print("4. Considerar optimizar la definicion de la vista materializada")
                return 1
                
    except Exception as e:
        logger.error(f"Error general: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
