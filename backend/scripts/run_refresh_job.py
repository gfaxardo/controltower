#!/usr/bin/env python3
"""
Script ejecutable para refresh de materialized views.
HARDENED: Lock anti-concurrencia + retry automático + registro granular.

Ejecutar: python scripts/run_refresh_job.py [--dataset DATASET_NAME]
"""
import sys
import os
import argparse

# Añadir backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.refresh_service import run_refresh_job, check_refresh_lock_status


def main():
    """Ejecuta el refresh job e imprime resultado."""
    parser = argparse.ArgumentParser(description='Refresh materialized views')
    parser.add_argument('--dataset', type=str, default=None, help='Nombre del dataset específico')
    args = parser.parse_args()
    
    print("=" * 70)
    print("REFRESH JOB - YEGO Control Tower (HARDENED)")
    print("=" * 70)
    
    # Verificar lock antes de empezar
    lock_status = check_refresh_lock_status()
    if lock_status.get("is_running"):
        print(f"\n[!] REFRESH SKIPPED")
        print(f"Another refresh is running since: {lock_status.get('started_at')}")
        print("Aborting to prevent concurrent execution.")
        sys.exit(0)
    
    print(f"\nDataset filter: {args.dataset or 'ALL'}")
    print(f"Max retries per dataset: 3")
    print(f"Retry delay: 10 seconds")
    print()
    
    # Ejecutar refresh
    result = run_refresh_job(dataset_filter=args.dataset)
    
    # Imprimir resultado
    print(f"\n{'=' * 70}")
    print("RESULTADO")
    print(f"{'=' * 70}")
    print(f"Status: {result['status'].upper()}")
    print(f"Timestamp: {result['timestamp']}")
    
    if result['status'] == 'skipped':
        print(f"\n[!] {result.get('message', 'Refresh skipped')}")
        sys.exit(0)
    
    if 'error' in result and result['error']:
        print(f"Error: {result['error']}")
    
    if 'datasets_processed' in result:
        print(f"\nDatasets processed: {result['datasets_processed']}")
        print(f"  OK Successful: {result.get('datasets_successful', 0)}")
        print(f"  X Failed: {result.get('datasets_failed', 0)}")
    
    if 'duration_seconds' in result:
        print(f"Total duration: {result['duration_seconds']}s")
    
    # Detalles por dataset
    if 'results' in result and result['results']:
        print(f"\n{'=' * 70}")
        print("DETALLES POR DATASET")
        print(f"{'=' * 70}")
        for r in result['results']:
            ds_name = r.get('dataset_name', 'unknown')
            status = r.get('status', 'unknown')
            
            if status == 'success':
                status_icon = '[ok]'
            elif status == 'skipped':
                status_icon = '[skip]'
            else:
                status_icon = '[err]'
            
            print(f"\n{status_icon} {ds_name}")
            print(f"   Status: {status}")
            print(f"   Duration: {r.get('duration_seconds', 0)}s")
            
            if r.get('error'):
                print(f"   Error: {r['error']}")
            
            # Mostrar intentos
            if 'attempts' in r:
                for att in r['attempts']:
                    att_icon = '+' if att['status'] == 'success' else ('!' if att['status'] == 'skipped' else 'x')
                    print(f"     Attempt {att['attempt']}: {att_icon} {att['status']} ({att.get('duration_seconds', 0)}s)")
                    if att.get('error'):
                        print(f"       → {att['error'][:80]}")
    
    print(f"\n{'=' * 70}")
    
    if result['status'] == 'success':
        print("REFRESH COMPLETED SUCCESSFULLY")
        sys.exit(0)
    elif result['status'] == 'partial_failure':
        print("[!] REFRESH PARTIALLY FAILED (some datasets failed)")
        sys.exit(1)
    else:
        print("REFRESH FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
