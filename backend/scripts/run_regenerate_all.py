"""
Ejecuta en secuencia los pasos para regenerar/refrescar vistas y MVs del frontend.

Pasos automáticos:
  1. Verificación inicial (objetos existan y sean consultables).
  2. Refresh MVs ops + opcionalmente Driver Lifecycle y Supply.
  3. Verificación final.

Uso:
  cd backend && python -m scripts.run_regenerate_all
  python -m scripts.run_regenerate_all --no-driver --no-supply   # solo MVs ops (más rápido)
  python -m scripts.run_regenerate_all --verify-only              # solo verificar
"""
import argparse
import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def run(cmd, timeout=None):
    """Ejecuta comando; timeout en segundos."""
    r = subprocess.run(
        cmd,
        cwd=BACKEND_DIR,
        timeout=timeout,
        capture_output=False,
        text=True,
    )
    return r.returncode


def main():
    parser = argparse.ArgumentParser(description="Regenerar vistas/MVs y verificar (pasos automáticos)")
    parser.add_argument("--no-driver", action="store_true", help="No ejecutar refresh driver lifecycle")
    parser.add_argument("--no-supply", action="store_true", help="No ejecutar refresh supply")
    parser.add_argument("--verify-only", action="store_true", help="Solo verificar (sin refrescar)")
    args = parser.parse_args()

    # Paso 1: verificación inicial
    logger.info("=== Paso 1: Verificación inicial ===")
    code = run(["python", "-m", "scripts.regenerate_views_and_verify", "--skip-refresh"], timeout=300)
    if code != 0:
        logger.error("Verificación inicial falló (código %s)", code)
        sys.exit(code)

    if not args.verify_only:
        # Paso 2: refresh MVs + driver + supply
        refresh_cmd = ["python", "-m", "scripts.regenerate_views_and_verify"]
        if not args.no_driver:
            refresh_cmd.append("--refresh-driver")
        if not args.no_supply:
            refresh_cmd.append("--refresh-supply")
        logger.info("=== Paso 2: Refresh MVs (driver=%s, supply=%s) ===", not args.no_driver, not args.no_supply)
        code = run(refresh_cmd, timeout=7200)
        if code != 0:
            logger.error("Refresh falló (código %s)", code)
            sys.exit(code)

        # Paso 3: verificación final
        logger.info("=== Paso 3: Verificación final ===")
        code = run(["python", "-m", "scripts.regenerate_views_and_verify", "--skip-refresh"], timeout=300)
        if code != 0:
            logger.error("Verificación final falló (código %s)", code)
            sys.exit(code)

    logger.info("Todos los pasos completados correctamente.")


if __name__ == "__main__":
    main()
