#!/usr/bin/env python3
"""
Driver Lifecycle v2 — Verificación automatizada (CI).
Ejecuta consistency validation + cohort validation.
Exit 0 = OK; exit != 0 = fallo.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.apply_driver_lifecycle_v2 import (
    run_consistency_validation,
    run_cohort_validation,
    quality_gates,
    cohort_mvs_exist,
    init_db_pool,
)
from app.db.connection import get_db


def main():
    init_db_pool()
    failed = False

    with get_db() as conn:
        ok_cons, fails = run_consistency_validation(conn, "verify")
        if not ok_cons or fails:
            print(f"FAIL: consistency validation — {len(fails)} filas con diff")
            for r in fails[:5]:
                print(f"  {r}")
            failed = True
        else:
            print("OK: consistency validation")

        if cohort_mvs_exist(conn):
            ok_cohort, msg = run_cohort_validation(conn)
            if not ok_cohort:
                print(f"FAIL: cohort validation — {msg}")
                failed = True
            else:
                print("OK: cohort validation")
        else:
            print("SKIP: cohort MVs no existen")

        ok_qg, _ = quality_gates(conn)
        if not ok_qg:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
