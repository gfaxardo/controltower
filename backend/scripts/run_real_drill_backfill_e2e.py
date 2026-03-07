"""
Ejecuta el flujo completo de backfill Real Drill y validación.

Orden:
  1. backfill_real_drill_service_by_park (tabla + vista por park/tipo_servicio)
  2. backfill_real_drill_service_type (filas breakdown=service_type en real_drill_dim_fact)
  3. check_real_drill_objects (validación)

Uso:
  python -m scripts.run_real_drill_backfill_e2e
  python -m scripts.run_real_drill_backfill_e2e --from 2025-12-01 --to 2026-03-31

Pasa --from y --to a ambos backfills. Chunk por defecto: weekly. --replace en ambos.
"""
import argparse
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Backfill Real Drill E2E + validación")
    parser.add_argument("--from", dest="from_", default="2025-12-01", help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--to", default="2026-03-31", help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--chunk", choices=["weekly", "monthly"], default="weekly", help="Chunk size")
    args = parser.parse_args()

    def run(module: str, extra: list[str] | None = None) -> int:
        cmd = [sys.executable, "-m", module, "--from", args.from_, "--to", args.to, "--chunk", args.chunk, "--replace"]
        if extra:
            cmd.extend(extra)
        print(f"\n>>> {module} ...", flush=True)
        r = subprocess.run(cmd, cwd=str(BACKEND_DIR))
        return r.returncode

    # 1. Backfill service by park
    if run("scripts.backfill_real_drill_service_by_park") != 0:
        print("run_real_drill_backfill_e2e: falló backfill_real_drill_service_by_park", flush=True)
        sys.exit(1)

    # 2. Backfill service_type en dim_fact
    if run("scripts.backfill_real_drill_service_type") != 0:
        print("run_real_drill_backfill_e2e: falló backfill_real_drill_service_type", flush=True)
        sys.exit(1)

    # 3. Validación (sin args de rango)
    print("\n>>> scripts.check_real_drill_objects ...", flush=True)
    r = subprocess.run([sys.executable, "-m", "scripts.check_real_drill_objects"], cwd=str(BACKEND_DIR))
    if r.returncode != 0:
        print("run_real_drill_backfill_e2e: validación falló", flush=True)
        sys.exit(1)

    print("\nrun_real_drill_backfill_e2e: flujo completo OK.", flush=True)


if __name__ == "__main__":
    main()
