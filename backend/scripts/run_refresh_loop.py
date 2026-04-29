#!/usr/bin/env python3
"""
Script de loop continuo para refresh de materialized views.
Ejecutar: python scripts/run_refresh_loop.py

Este script corre indefinidamente, ejecutando refresh cada 30 minutos.
Maneja excepciones globales para nunca terminar.
"""
import sys
import os
import time
import traceback
from datetime import datetime

# Añadir backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.refresh_service import run_refresh_job

# Intervalo entre ejecuciones (30 minutos = 1800 segundos)
INTERVAL_SECONDS = 1800


def log_message(msg: str, level: str = "INFO"):
    """Imprime mensaje con timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")
    sys.stdout.flush()


def main():
    """Loop principal de refresh."""
    log_message("=" * 70)
    log_message("REFRESH LOOP - YEGO Control Tower")
    log_message("=" * 70)
    log_message(f"Interval: {INTERVAL_SECONDS} seconds ({INTERVAL_SECONDS / 60} minutes)")
    log_message("Press Ctrl+C to stop")
    log_message("=" * 70)
    
    iteration = 0
    
    while True:
        iteration += 1
        log_message(f"\n--- Iteration #{iteration} ---")
        
        try:
            # Ejecutar refresh
            log_message("Starting refresh job...")
            result = run_refresh_job()
            
            # Log resultado
            if result['status'] == 'success':
                log_message(
                    f"✅ Refresh completed: {result.get('datasets_successful', 0)}/{result.get('datasets_processed', 0)} datasets, "
                    f"{result.get('duration_seconds', 0)}s",
                    "SUCCESS"
                )
            elif result['status'] == 'skipped':
                log_message(f"⚠️  Refresh skipped: {result.get('message', 'Another job running')}", "WARN")
            else:
                log_message(
                    f"❌ Refresh failed: {result.get('datasets_failed', 0)}/{result.get('datasets_processed', 0)} datasets failed, "
                    f"{result.get('duration_seconds', 0)}s",
                    "ERROR"
                )
                if result.get('error'):
                    log_message(f"Error: {result['error']}", "ERROR")
                    
        except KeyboardInterrupt:
            log_message("\n🛑 Stopped by user (Ctrl+C)", "INFO")
            sys.exit(0)
            
        except Exception as e:
            log_message(f"💥 UNEXPECTED ERROR: {str(e)}", "CRITICAL")
            log_message(traceback.format_exc(), "CRITICAL")
            # Continuar - nunca terminar el loop
        
        # Esperar hasta la siguiente ejecución
        log_message(f"Sleeping for {INTERVAL_SECONDS} seconds...")
        try:
            time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            log_message("\n🛑 Stopped by user (Ctrl+C)", "INFO")
            sys.exit(0)


if __name__ == "__main__":
    main()
