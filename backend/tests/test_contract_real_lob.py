"""
Test CI: ejecuta el contract check REAL LOB Observability.
"""
import os
import subprocess
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(BACKEND_DIR, "scripts", "contract_check_real_lob.py")
REPO_ROOT = os.path.dirname(BACKEND_DIR)


@pytest.mark.skipif(
    not os.path.isfile(SCRIPT),
    reason="contract_check_real_lob.py not found",
)
def test_contract_check_real_lob():
    """Ejecuta contract_check_real_lob.py; exit 0 = PASS."""
    env = os.environ.copy()
    env["PYTHONPATH"] = BACKEND_DIR + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Contract check REAL LOB failed (exit {result.returncode}).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
