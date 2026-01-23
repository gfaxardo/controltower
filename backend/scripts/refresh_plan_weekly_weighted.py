#!/usr/bin/env python3
"""
Script para refresh de Plan Semanal con weights basados en baseline por país.
MODO SAFE: No ejecuta materialización hasta que se complete el download.

Uso:
    python refresh_plan_weekly_weighted.py --dry-run    # Solo reporta
    python refresh_plan_weekly_weighted.py --execute    # Aborta con mensaje claro
"""
import sys
import os
import argparse
from datetime import date, datetime

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_baseline_by_country():
    """Obtiene baseline efectivo por país desde la vista."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT 
                    country,
                    baseline_tag,
                    baseline_start_date,
                    baseline_end_date
                FROM ops.v_plan_weekly_baseline_effective
                ORDER BY country
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error al obtener baselines: {e}")
        raise


def get_coverage_by_key(min_coverage=0.80, min_trips=1000):
    """
    Obtiene cobertura real por key desde la vista.
    Parámetros configurables: min_coverage (default 0.80), min_trips (default 1000).
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT 
                    country,
                    city_norm,
                    lob_base,
                    segment,
                    baseline_tag,
                    baseline_start_date,
                    baseline_end_date,
                    days_present,
                    days_expected,
                    coverage_pct,
                    trips_present,
                    ready
                FROM ops.v_real_coverage_baseline_by_key
                ORDER BY country, city_norm, lob_base, segment
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error al obtener cobertura: {e}")
        raise


def report_baselines():
    """Reporta baseline por país."""
    logger.info("=" * 80)
    logger.info("BASELINES POR PAÍS")
    logger.info("=" * 80)
    
    baselines = get_baseline_by_country()
    
    if not baselines:
        logger.warning("No se encontraron baselines activos")
        return
    
    for baseline in baselines:
        logger.info(f"País: {baseline.get('country', 'GLOBAL')}")
        logger.info(f"  Tag: {baseline.get('baseline_tag')}")
        logger.info(f"  Período: {baseline.get('baseline_start_date')} a {baseline.get('baseline_end_date')}")
        logger.info("")


def report_coverage(dry_run=True):
    """Reporta cobertura por key, destacando keys no-ready."""
    logger.info("=" * 80)
    logger.info("COBERTURA REAL SOBRE BASELINE")
    logger.info("=" * 80)
    
    coverage = get_coverage_by_key()
    
    if not coverage:
        logger.warning("No se encontraron datos de cobertura")
        return
    
    ready_count = sum(1 for c in coverage if c.get('ready'))
    total_count = len(coverage)
    
    logger.info(f"Total keys: {total_count}")
    logger.info(f"Keys ready: {ready_count}")
    logger.info(f"Keys no-ready: {total_count - ready_count}")
    logger.info("")
    
    # Agrupar por país
    by_country = {}
    for c in coverage:
        country = c.get('country', 'UNKNOWN')
        if country not in by_country:
            by_country[country] = {'ready': [], 'not_ready': []}
        if c.get('ready'):
            by_country[country]['ready'].append(c)
        else:
            by_country[country]['not_ready'].append(c)
    
    for country, data in sorted(by_country.items()):
        logger.info(f"País: {country}")
        logger.info(f"  Ready: {len(data['ready'])}")
        logger.info(f"  No-ready: {len(data['not_ready'])}")
        
        if data['not_ready'] and dry_run:
            logger.info("  Keys NO-READY:")
            for key in data['not_ready'][:10]:  # Mostrar primeros 10
                logger.info(f"    {key.get('city_norm')} | {key.get('lob_base')} | {key.get('segment')}")
                logger.info(f"      Coverage: {key.get('coverage_pct', 0):.2%} | Trips: {key.get('trips_present', 0):,} | Baseline: {key.get('baseline_tag')}")
            if len(data['not_ready']) > 10:
                logger.info(f"    ... y {len(data['not_ready']) - 10} más")
        logger.info("")


def main():
    parser = argparse.ArgumentParser(
        description='Refresh Plan Semanal con weights basados en baseline por país (MODO SAFE)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Solo reporta baselines y cobertura, no ejecuta materialización'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Intenta ejecutar (pero aborta con mensaje claro)'
    )
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        parser.print_help()
        sys.exit(1)
    
    try:
        # Siempre reportar baselines
        report_baselines()
        
        # Reportar cobertura
        report_coverage(dry_run=args.dry_run)
        
        if args.execute:
            logger.error("=" * 80)
            logger.error("ABORT: Not executing weights/materialization until download complete")
            logger.error("=" * 80)
            logger.error("El sistema está en modo SAFE.")
            logger.error("No se materializará el plan semanal hasta que se complete el download.")
            logger.error("Use --dry-run para solo reportar estado.")
            sys.exit(1)
        
        logger.info("=" * 80)
        logger.info("MODO DRY-RUN completado exitosamente")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error en ejecución: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
