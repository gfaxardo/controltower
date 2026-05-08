"""
Mediciones internas por etapa (sin HTTP) para GET /ops/business-slice/monthly.

Uso (desde carpeta backend):
  python scripts/profile_omniview_monthly_stages.py

Requiere DATABASE_URL / DB_*.
"""
from __future__ import annotations

import os
import sys
import time

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import app.services.business_slice_service as bss

get_business_slice_monthly = bss.get_business_slice_monthly
get_business_slice_matrix_freshness_meta = bss.get_business_slice_matrix_freshness_meta
enrich_business_slice_matrix_meta = bss.enrich_business_slice_matrix_meta
merge_unmapped_bucket_rows_monthly = bss.merge_unmapped_bucket_rows_monthly
compute_matrix_data_freshness = bss.compute_matrix_data_freshness
_safe_fetch_matrix_totals_meta = bss._safe_fetch_matrix_totals_meta


def main() -> None:
    t0 = time.perf_counter()
    rows = get_business_slice_monthly()
    m1 = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    rows2, unmapped_tot = merge_unmapped_bucket_rows_monthly(rows)
    m2 = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    _ = compute_matrix_data_freshness(
        "monthly",
        country=None,
        city=None,
        business_slice=None,
        fleet=None,
        subfleet=None,
        year=None,
        month=None,
    )
    m3 = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    _ = _safe_fetch_matrix_totals_meta(
        "monthly",
        rows2,
        unmapped_period_totals_precomputed=unmapped_tot,
        profile=None,
    )
    m4 = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    _ = enrich_business_slice_matrix_meta(
        get_business_slice_matrix_freshness_meta(),
        "monthly",
        rows2,
        unmapped_period_totals_precomputed=unmapped_tot,
        profile=None,
    )
    m5 = (time.perf_counter() - t0) * 1000

    wall1 = m1
    wall2 = m1 + m2
    wall3 = wall2 + m3
    wall4 = wall3 + m4
    wall5 = wall4 + m5

    print("Bloques aislados (incremental, mismo orden lógico que el endpoint):")
    print(f"  1 monthly base (MV + attach partial equiv): {m1:.1f} ms  rows={len(rows)}")
    print(f"  2 append UNMAPPED:                         {m2:.1f} ms")
    print(f"  3 freshness (consulta day_fact scope):      {m3:.1f} ms")
    print(f"  4 matrix_totals meta (_safe_fetch solamente): {m4:.1f} ms")
    print(f"  5 enrich meta completo (incl. 4 de nuevo + slice_max + period_states): {m5:.1f} ms")
    print("")
    print("Cumulative aproximado (suma 1..k, solo orientativo; 4 está contenido en 5):")
    print(f"  after 1: {wall1:.1f} ms")
    print(f"  after 2: {wall2:.1f} ms")
    print(f"  after 3: {wall3:.1f} ms")
    print(f"  after 4: {wall4:.1f} ms")
    print(f"  after 5: {wall5:.1f} ms  (no igual a HTTP: 5 repite trabajo de 4)")


if __name__ == "__main__":
    main()
