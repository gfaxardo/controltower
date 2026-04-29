#!/usr/bin/env python3
"""
Script ejecutable para refresh de materialized views.
Ejecutar: python scripts/run_refresh_job.py
"""
import sys
import os

# Añadir backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.refresh_service import run_refresh_job


def main():
    """Ejecuta el refresh job e imprime resultado."""
    print("=" * 60)
    print("REFRESH JOB - YEGO Control Tower")
    print("=" * 60)
    
    # Ejecutar refresh
    result = run_refresh_job()
    
    # Imprimir resultado
    print(f"\nDataset: {result['dataset_name']}")
    print(f"Status: {result['status'].upper()}")
    print(f"Duration: {result['duration_seconds']}s")
    print(f"Functions executed: {result['functions_executed']}")
    print(f"Timestamp: {result['timestamp']}")
    
    if result['error']:
        print(f"\nERROR: {result['error']}")
        print("\n❌ REFRESH FAILED")
        sys.exit(1)
    
    # Detalles por función
    if result['results']:
        print("\nDetails:")
        for r in result['results']:
            status_icon = "✓" if r['status'] == 'success' else ("⚠" if r['status'] == 'skipped' else "✗")
            print(f"  {status_icon} {r['function']}: {r['status']}")
            if 'duration_seconds' in r:
                print(f"    Duration: {r['duration_seconds']}s")
            if 'error' in r and r['error']:
                print(f"    Error: {r['error']}")
    
    if result['status'] == 'success':
        print("\n✅ REFRESH COMPLETED SUCCESSFULLY")
        sys.exit(0)
    else:
        print("\n❌ REFRESH FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
