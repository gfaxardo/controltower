"""
Ejecuta en secuencia: paridad global, pe, co y análisis de diferencias.
Resiliente: timeout por paso, escribe log y CSV aunque falle uno.
Uso: python -m scripts.run_plan_vs_real_parity_e2e [--timeout 120]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

BACKEND = Path(__file__).resolve().parent.parent
OUT = BACKEND / "outputs"
LOG = OUT / "parity_run_log.txt"


def run(cmd: list[str], label: str, timeout: int) -> tuple[int, str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**__import__("os").environ, "PYTHONPATH": str(BACKEND)}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now(timezone.utc).isoformat()}] === {label} ===\n")
    try:
        r = subprocess.run(
            cmd,
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"exit={r.returncode}\n")
            f.write(r.stdout[:3000] + "\n")
            if r.stderr:
                f.write("stderr: " + r.stderr[:1000] + "\n")
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"TIMEOUT after {timeout}s\n")
        return -1, "", "timeout"
    except Exception as e:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"ERROR: {e}\n")
        return -2, "", str(e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=120, help="Timeout por paso (segundos)")
    args = ap.parse_args()
    t = args.timeout

    steps = [
        ("global_2025", [sys.executable, "-m", "scripts.validate_plan_vs_real_parity", "--year", "2025", "--out", "outputs/plan_vs_real_parity_2025.csv", "--save-audit"]),
        ("pe_2025", [sys.executable, "-m", "scripts.validate_plan_vs_real_parity", "--year", "2025", "--country", "pe", "--save-audit"]),
        ("co_2025", [sys.executable, "-m", "scripts.validate_plan_vs_real_parity", "--year", "2025", "--country", "co", "--save-audit"]),
        ("diff_analysis", [sys.executable, "-m", "scripts.analyze_plan_vs_real_diffs", "--year", "2025", "--out", "outputs/plan_vs_real_diff_analysis_2025.csv"]),
    ]
    for label, cmd in steps:
        code, out, err = run(cmd, label, t)
        status = "OK" if code == 0 else f"FAIL({code})"
        print(f"{label}: {status}")
        if code == 0 and "DIAGNOSIS:" in out:
            for line in out.splitlines():
                if line.startswith("DIAGNOSIS:") or line.startswith("DATA_COMPLETENESS:"):
                    print(f"  {line.strip()}")
    print(f"\nLog: {LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
