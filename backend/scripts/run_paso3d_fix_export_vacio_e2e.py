"""
Runner: ejecuta paso3d_fix_export_vacio_e2e y termina con exit 0 si éxito, 1 si falla.
"""
import sys
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)

if __name__ == "__main__":
    r = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "paso3d_fix_export_vacio_e2e.py")],
        cwd=BACKEND_DIR,
        timeout=700,
    )
    sys.exit(r.returncode)
