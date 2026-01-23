#!/usr/bin/env python3
"""
Script para refrescar la vista materializada ops.mv_real_trips_monthly (v2 ya swap).
con manejo de timeout.
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

def refresh_mv_v2(conn, timeout_seconds=7200):
    """
    Refresca la vista materializada principal (v2 ya swap).
    """
    cursor = conn.cursor()
    try:
        # Establecer timeout para esta sesión
        cursor.execute(f"SET statement_timeout = '{timeout_seconds * 1000}ms'")
        logger.info(f"Timeout configurado a {timeout_seconds} segundos")
        
        logger.info("Iniciando REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly...")
        start_time = time.time()
        
        cursor.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly")
        conn.commit()
        
        elapsed = time.time() - start_time
        logger.info(f"Refresh completado en {elapsed:.2f} segundos")
        return True, elapsed
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Refresh fallo: {error_msg}")
        if 'timeout' in error_msg.lower() or '57014' in error_msg:
            logger.error("Timeout detectado. Considera aumentar el timeout.")
        conn.rollback()
        return False, None

def check_mv_v2_status(conn):
    """Verifica el estado de la MV v2"""
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
        else:
            logger.warning("MV v2 no existe. Ejecuta la migracion 013 primero.")
            return
        
        # Conteo de registros
        cursor.execute("SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly;")
        count = cursor.fetchone()['count']
        logger.info(f"  Total de registros: {count:,}")
        
        # Última actualización
        cursor.execute("SELECT MAX(refreshed_at) as last_refresh FROM ops.mv_real_trips_monthly")
        refresh_info = cursor.fetchone()
        if refresh_info and refresh_info['last_refresh']:
            logger.info(f"  Ultima actualizacion: {refresh_info['last_refresh']}")
        
    except Exception as e:
        logger.warning(f"Error al verificar estado: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Refrescar vista materializada ops.mv_real_trips_monthly (v2 swap)')
    parser.add_argument('--timeout', type=int, default=7200, 
                       help='Timeout en segundos (default: 7200 = 2 horas)')
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
            check_mv_v2_status(conn)
            
            if args.check_only:
                print("\n[Modo check-only: no se ejecutara refresh]")
                return 0
            
            # Ejecutar refresh
            print(f"\n2. Ejecutando refresh (timeout: {args.timeout}s)...")
            success, elapsed = refresh_mv_v2(conn, args.timeout)
            
            if success:
                print("\n" + "=" * 80)
                print("REFRESH COMPLETADO EXITOSAMENTE")
                print("=" * 80)
                print(f"Tiempo transcurrido: {elapsed:.2f} segundos")
                
                # Verificar nueva fecha de actualización
                print("\n3. Verificando nueva fecha de actualizacion...")
                check_mv_v2_status(conn)
                return 0
            else:
                print("\n" + "=" * 80)
                print("REFRESH FALLO")
                print("=" * 80)
                return 1
                
    except Exception as e:
        logger.error(f"Error general: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
