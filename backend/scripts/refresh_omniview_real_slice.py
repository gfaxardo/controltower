#!/usr/bin/env python3
"""
DEPRECATED — CF-H1J.7: este script legacy esta BLOQUEADO para uso productivo.

El loader legacy usa la vista enriquecida que escanea millones de filas.
Para refresh productivo usa el incremental:
  python -m scripts.refresh_omniview_real_slice_incremental --start-date <fecha> --end-date <fecha> --grain all

Para bypass de emergencia (solo con autorizacion explicita):
  python -m scripts.refresh_omniview_real_slice --allow-legacy-weekly-dangerous
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LEGACY_BLOCK_MSG = (
    "NO-GO: refresh_omniview_real_slice.py esta DEPRECATED.\n"
    "Este loader puede producir week_fact incompleta o corrupta.\n"
    "Usa el incremental refresh:\n"
    "  python -m scripts.refresh_omniview_real_slice_incremental\n"
    "  --start-date <fecha_inicio> --end-date <fecha_fin> --grain all\n"
    "\n"
    "Si realmente necesitas ejecutar este script legacy, usa:\n"
    "  --allow-legacy-weekly-dangerous\n"
    "  Solo para backfill historico controlado, NUNCA para refresh productivo."
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="DEPRECATED — use incremental refresh instead."
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Ignora cooldown OMNIVIEW_REAL_REFRESH_MIN_INTERVAL_MINUTES.",
    )
    ap.add_argument(
        "--allow-legacy-weekly-dangerous",
        action="store_true",
        help="Bypass explicito del bloqueo de seguridad. Solo para backfill historico.",
    )
    args = ap.parse_args()

    if not args.allow_legacy_weekly_dangerous:
        print(LEGACY_BLOCK_MSG, file=sys.stderr)
        return 1

    from app.services.business_slice_real_refresh_job import run_business_slice_real_refresh_job

    print(
        "WARNING: Ejecutando legacy loader con --allow-legacy-weekly-dangerous. "
        "Esto NO debe usarse para refresh productivo.",
        file=sys.stderr,
    )
    out = run_business_slice_real_refresh_job(force=args.force)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
