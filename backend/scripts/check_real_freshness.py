#!/usr/bin/env python3
"""
CLI: mismo payload que GET /ops/business-slice/real-freshness (upstream + agregado).

Uso:
  cd backend
  python -m scripts.check_real_freshness
  python -m scripts.check_real_freshness --fail-on critical empty

Exit code 1 si el status global está en la lista --fail-on (default: critical, empty).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.business_slice_real_freshness_service import build_omniview_real_freshness_payload


def main() -> int:
    p = argparse.ArgumentParser(description="Comprobar freshness REAL Omniview (upstream + facts).")
    p.add_argument(
        "--fail-on",
        nargs="*",
        default=["critical", "empty"],
        metavar="STATUS",
        help="Estados que devuelven exit 1 (default: critical empty)",
    )
    args = p.parse_args()
    fail_set = {s.strip().lower() for s in (args.fail_on or []) if s}

    payload = build_omniview_real_freshness_payload()
    print(json.dumps(payload, indent=2, default=str))

    st = (payload.get("status") or payload.get("overall_status") or "unknown").lower()
    if st in fail_set:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
