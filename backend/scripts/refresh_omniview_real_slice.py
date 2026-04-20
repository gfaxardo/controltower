#!/usr/bin/env python3
"""
CLI: recarga operacional ops.real_business_slice_day_fact + week_fact
(mes actual y anterior) — mismo job que APScheduler y POST /ops/business-slice/real-refresh-omniview.

Uso:
  cd backend
  python -m scripts.refresh_omniview_real_slice
  python -m scripts.refresh_omniview_real_slice --force

Salida: JSON con ok, duration_seconds, errors, freshness_after.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.business_slice_real_refresh_job import run_business_slice_real_refresh_job


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--force",
        action="store_true",
        help="Ignora cooldown OMNIVIEW_REAL_REFRESH_MIN_INTERVAL_MINUTES.",
    )
    args = ap.parse_args()
    out = run_business_slice_real_refresh_job(force=args.force)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
