"""
[YEGO CT] E2E PASO A — Ejecutar todos los pasos en secuencia.
1) pasoA1: exporta real_catalog_for_plan.csv
2) Genera plan_realkey_from_catalog.csv desde el catálogo (plan mínimo)
3) pasoA2: TRUNCATE + carga plan realkey
4) pasoA3: smoke Plan vs Real

Uso: python scripts/pasoA_e2e_todo.py
     python scripts/pasoA_e2e_todo.py --skip-plan-catalog   # no regenerar plan desde catálogo (usa CSV existente)
"""
import argparse
import os
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
PLAN_CSV = os.path.join(EXPORTS_DIR, "plan_realkey_from_catalog.csv")


def run(desc: str, cmd: list, timeout: int = 600) -> bool:
    print("\n" + "=" * 60)
    print(f"  {desc}")
    print("=" * 60)
    r = subprocess.run(cmd, cwd=BACKEND_DIR, timeout=timeout)
    ok = r.returncode == 0
    if not ok:
        print(f"  [FALLO] Código {r.returncode}")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-plan-catalog", action="store_true", help="No generar plan desde catálogo; usar CSV existente")
    args = parser.parse_args()

    os.makedirs(EXPORTS_DIR, exist_ok=True)

    # 1) Paso A.1
    if not run("PASO A.1 — Export real_catalog_for_plan.csv", [sys.executable, "scripts/pasoA1_export_real_catalog_for_plan.py"], timeout=300):
        sys.exit(1)

    # 2) Plan desde catálogo (a menos que se pida skip)
    if not args.skip_plan_catalog:
        if not run("Generar plan_realkey desde catálogo", [sys.executable, "scripts/build_plan_realkey_from_catalog.py"], timeout=30):
            sys.exit(1)
    if not os.path.isfile(PLAN_CSV):
        print(f"\n  [ERROR] No existe {PLAN_CSV}. Ejecuta sin --skip-plan-catalog o crea el CSV manualmente.")
        sys.exit(1)

    # 3) Paso A.2
    if not run("PASO A.2 — Cargar plan realkey", [sys.executable, "scripts/pasoA2_load_plan_realkey.py", "--csv", PLAN_CSV], timeout=120):
        sys.exit(1)

    # 4) Paso A.3 (vista real puede tardar; 10 min)
    if not run("PASO A.3 — Smoke Plan vs Real", [sys.executable, "scripts/pasoA3_smoke_plan_vs_real_realkey.py"], timeout=660):
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  PASO A E2E — TODO OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
