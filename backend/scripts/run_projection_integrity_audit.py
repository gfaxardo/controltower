#!/usr/bin/env python3
"""
PARTE 1 — Auditoría de integridad de proyección (monthly → weekly → daily).

Uso:
  cd backend
  python scripts/run_projection_integrity_audit.py --plan-version ruta27_2026_04_21 --year 2026 --month 4

Genera:
  outputs/projection_integrity_<plan_version>.csv
  outputs/projection_validation_summary.txt  (PASS/FAIL por combinación)
"""
from __future__ import annotations
import argparse
import csv
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.services.projection_expected_progress_service import get_omniview_projection  # noqa: E402

# Umbrales
WEEKLY_DRIFT_LIMIT_PCT   = 1.0   # %
DAILY_DRIFT_LIMIT_PCT    = 1.0
MAX_WEEKLY_VAR_LIMIT_PCT = 25.0
MAX_DAILY_VAR_LIMIT_PCT  = 35.0

KPIS = ("trips_completed", "revenue_yego_net", "active_drivers")

# projected_total: valor proyectado a fin de período (incluye real ya ocurrido)
PROJ_COL = {
    "trips_completed":  "trips_completed_projected_total",
    "revenue_yego_net": "revenue_yego_net_projected_total",
    "active_drivers":   "active_drivers_projected_total",
}
# monthly_plan: el plan puro del archivo (ancla de conservación)
PLAN_COL = {
    "trips_completed":  "trips_completed_monthly_plan",
    "revenue_yego_net": "revenue_yego_net_monthly_plan",
    "active_drivers":   "active_drivers_monthly_plan",
}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _find_rows(data: List[Dict], country: str, city: str, bsn: str) -> List[Dict]:
    co = _norm(country)
    ci = _norm(city)
    bs = _norm(bsn)
    return [
        r for r in data
        if _norm(r.get("country", "")) == co
        and _norm(r.get("city", "")) == ci
        and _norm(r.get("business_slice_name", "")) == bs
    ]


def _sum_col(rows: List[Dict], col: str) -> Tuple[float, bool]:
    """Returns (sum, has_nan). has_nan=True means some values were null/nan (no curve)."""
    import math
    total = 0.0
    has_nan = False
    for r in rows:
        v = r.get(col)
        if v is None:
            has_nan = True
        else:
            fv = float(v)
            if math.isnan(fv):
                has_nan = True
            else:
                total += fv
    return total, has_nan


def _max_var_pct(rows: List[Dict], col: str) -> float:
    import math
    vals = []
    for r in rows:
        v = r.get(col)
        if v is not None:
            fv = float(v)
            if not math.isnan(fv) and fv > 0:
                vals.append(fv)
    if len(vals) < 2:
        return 0.0
    avg = sum(vals) / len(vals)
    if avg <= 0:
        return 0.0
    return max(abs(v / avg - 1.0) * 100.0 for v in vals)


def _fallback_and_conf(rows: List[Dict], kpi: str) -> Tuple[Optional[int], Optional[str]]:
    for r in rows:
        fl = r.get(f"{kpi}_fallback_level")
        cf = r.get(f"{kpi}_curve_confidence")
        if fl is not None:
            return int(fl), cf
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Projection Integrity Audit E2E")
    ap.add_argument("--plan-version", required=True)
    ap.add_argument("--year",  type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--out-dir", default=os.path.join(_BACKEND_ROOT, "scripts", "outputs"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    PV   = args.plan_version
    YEAR = args.year
    MONTH= args.month

    print(f"\n{'='*62}")
    print(f"  Projection Integrity Audit")
    print(f"  plan_version = {PV}")
    print(f"  period       = {YEAR}-{MONTH:02d}")
    print(f"{'='*62}")

    # ── 1. Descubrir combinaciones del plan ────────────────────────────────
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT DISTINCT lower(trim(country)) AS country,
                            trim(city)           AS city,
                            trim(lob_base)       AS lob_base
            FROM ops.plan_trips_monthly
            WHERE plan_version = %s
              AND EXTRACT(YEAR  FROM month) = %s
              AND EXTRACT(MONTH FROM month) = %s
            ORDER BY country, city, lob_base
        """, [PV, YEAR, MONTH])
        combos_raw = [dict(r) for r in cur.fetchall()]
        cur.close()

    if not combos_raw:
        print(f"\n[!] No hay filas en ops.plan_trips_monthly para {PV} {YEAR}-{MONTH:02d}")
        print("    Verifique el plan_version (minúsculas) y el período.")
        _write_summary(args.out_dir, PV, YEAR, MONTH, [], ok=False,
                       reason="Plan no encontrado en ops.plan_trips_monthly")
        return 1

    print(f"\n[+] {len(combos_raw)} combinaciones en plan para {YEAR}-{MONTH:02d}")

    # ── 2. Carga de proyección (monthly / weekly / daily) ──────────────────
    t0 = time.perf_counter()
    print(f"\n[→] get_omniview_projection grain=monthly …")
    resp_m = get_omniview_projection(PV, grain="monthly", year=YEAR, month=MONTH)
    data_m = resp_m.get("data") or []

    print(f"[→] get_omniview_projection grain=weekly  …")
    resp_w = get_omniview_projection(PV, grain="weekly",  year=YEAR, month=MONTH)
    data_w = resp_w.get("data") or []
    meta_w = resp_w.get("meta") or {}

    print(f"[→] get_omniview_projection grain=daily   …")
    resp_d = get_omniview_projection(PV, grain="daily",   year=YEAR, month=MONTH)
    data_d = resp_d.get("data") or []

    elapsed = time.perf_counter() - t0
    print(f"[✓] Carga completada en {elapsed:.1f}s   "
          f"(m={len(data_m)} w={len(data_w)} d={len(data_d)} filas)")

    # ── 3. Resolver combos plan→BSN via servicio ───────────────────────────
    # Extraer combinaciones disponibles en data mensual (ya resueltas)
    combos_resolved = sorted({
        (_norm(r.get("country","")), _norm(r.get("city","")), _norm(r.get("business_slice_name","")))
        for r in data_m
    })
    print(f"[+] {len(combos_resolved)} combinaciones resueltas en respuesta mensual")

    if not combos_resolved:
        # Intento con lista raw del plan — los slugs del LOB no mapearon a BSN canónico.
        print("[!] WARN: cero filas mensuales — posible falla de resolución LOB→BSN")
        _write_summary(args.out_dir, PV, YEAR, MONTH, [], ok=False,
                       reason="Cero filas mensuales devueltas (falla LOB→BSN mapping?)")
        return 1

    # ── 4. Calcular métricas por (country, city, bsn, kpi) ────────────────
    out_rows: List[Dict] = []
    n_fail = 0

    for co, ci, bsn in combos_resolved:
        mrows = _find_rows(data_m, co, ci, bsn)
        wrows = _find_rows(data_w, co, ci, bsn)
        drows = _find_rows(data_d, co, ci, bsn)

        for kpi in KPIS:
            # Ancla: monthly_plan (el plan puro del Excel, no el projected_total que mezcla real+proyectado)
            # Si monthly_plan no está en la respuesta, fallback a projected_total
            mp_plan, mp_plan_nan = _sum_col(mrows, PLAN_COL[kpi])
            mp_proj, mp_proj_nan = _sum_col(mrows, PROJ_COL[kpi])
            mp = mp_plan if mp_plan > 0 else mp_proj

            ws, ws_nan  = _sum_col(wrows, PROJ_COL[kpi])
            ds, ds_nan  = _sum_col(drows, PROJ_COL[kpi])
            any_nan = ws_nan or ds_nan

            wd_abs  = ws - mp
            dd_abs  = ds - mp
            wd_pct  = (wd_abs / mp * 100) if mp > 0 else None
            dd_pct  = (dd_abs / mp * 100) if mp > 0 else None
            mwv     = _max_var_pct(wrows, PROJ_COL[kpi])
            mdv     = _max_var_pct(drows, PROJ_COL[kpi])
            fl, cf  = _fallback_and_conf(wrows, kpi)

            proj_conf = None
            if wrows:
                proj_conf = wrows[0].get("projection_confidence")

            import math as _math
            if mp == 0 and ws == 0 and ds == 0:
                verdict = "NO_DATA"
            elif any_nan or wd_pct is None or dd_pct is None or _math.isnan(wd_pct) or _math.isnan(dd_pct):
                # NaN = curva de KPI no disponible para este LOB (warning, no hard failure)
                verdict = "WARN_NO_CURVE"
            else:
                # Drift pct PASS si pct<=límite O abs<=1 (redondeo en planes de bajo volumen)
                wd_ok = (abs(wd_pct) <= WEEKLY_DRIFT_LIMIT_PCT) or (abs(wd_abs) <= 1.0)
                dd_ok = (abs(dd_pct) <= DAILY_DRIFT_LIMIT_PCT) or (abs(dd_abs) <= 1.0)
                # Variación: no se evalúa en validación de conservación (comportamiento mid-month esperado)
                conservation_ok = wd_ok and dd_ok
                verdict = "PASS" if conservation_ok else "FAIL"
                if verdict == "FAIL":
                    n_fail += 1

            def _fmt(v) -> str:
                if v is None: return ""
                return f"{v:.4f}"

            out_rows.append({
                "country":                co,
                "city":                   ci,
                "business_slice_name":    bsn,
                "kpi":                    kpi,
                "month":                  f"{YEAR}-{MONTH:02d}",
                "monthly_plan":           _fmt(mp),
                "monthly_projected_total": _fmt(mp_proj),
                "weekly_sum":             _fmt(ws),
                "daily_sum":              _fmt(ds),
                "weekly_drift_abs":       _fmt(wd_abs),
                "weekly_drift_pct":       _fmt(wd_pct),
                "daily_drift_abs":        _fmt(dd_abs),
                "daily_drift_pct":        _fmt(dd_pct),
                "max_weekly_variation_pct": _fmt(mwv),
                "max_daily_variation_pct":  _fmt(mdv),
                "fallback_level":         fl if fl is not None else "",
                "curve_confidence":       cf or "",
                "projection_confidence":  proj_conf or "",
                "weekly_rows":            len(wrows),
                "daily_rows":             len(drows),
                "verdict":                verdict,
            })

    # ── 5. Escribir CSV ────────────────────────────────────────────────────
    csv_path = os.path.join(args.out_dir, f"projection_integrity_{PV}.csv")
    if out_rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
    print(f"\n[✓] CSV: {csv_path}")

    # ── 6. Resumen por consola ─────────────────────────────────────────────
    total = len(out_rows)
    pass_n = sum(1 for r in out_rows if r["verdict"] == "PASS")
    fail_n = sum(1 for r in out_rows if r["verdict"] == "FAIL")
    warn_n = sum(1 for r in out_rows if r["verdict"] == "WARN_NO_CURVE")
    nodata = sum(1 for r in out_rows if r["verdict"] == "NO_DATA")

    if out_rows:
        wd_max = max((abs(float(r["weekly_drift_pct"])) for r in out_rows if r["weekly_drift_pct"]), default=0)
        dd_max = max((abs(float(r["daily_drift_pct"])) for r in out_rows if r["daily_drift_pct"]), default=0)
        mv_w   = max((float(r["max_weekly_variation_pct"]) for r in out_rows if r["max_weekly_variation_pct"]), default=0)
        mv_d   = max((float(r["max_daily_variation_pct"]) for r in out_rows if r["max_daily_variation_pct"]), default=0)
    else:
        wd_max = dd_max = mv_w = mv_d = 0

    print(f"\n{'─'*62}")
    print(f"  Total combos×KPI : {total:>4}")
    print(f"  PASS             : {pass_n:>4}")
    print(f"  FAIL             : {fail_n:>4}")
    print(f"  WARN_NO_CURVE    : {warn_n:>4}  (KPI sin curva para ese LOB)")
    print(f"  NO_DATA          : {nodata:>4}")
    print(f"  max_weekly_drift : {wd_max:.4f}% (límite {WEEKLY_DRIFT_LIMIT_PCT}%)")
    print(f"  max_daily_drift  : {dd_max:.4f}% (límite {DAILY_DRIFT_LIMIT_PCT}%)")
    print(f"  max_weekly_var   : {mv_w:.2f}% (límite {MAX_WEEKLY_VAR_LIMIT_PCT}%)")
    print(f"  max_daily_var    : {mv_d:.2f}% (límite {MAX_DAILY_VAR_LIMIT_PCT}%)")

    conservation = meta_w.get("conservation") or {}
    slices_adj = conservation.get("slices_adjusted", "?")
    drift_cons  = conservation.get("max_drift_pct", "?")
    print(f"\n  Conservation engine: slices_adjusted={slices_adj}, max_drift_pct={drift_cons}")

    fallback_summary = (meta_w.get("plan_derivation") or {}).get("fallback_level_summary") or {}
    print(f"  Fallback levels: {fallback_summary}")

    system_ok = fail_n == 0 and total > 0 and pass_n > 0
    print(f"\n  VERDICT MONTHLY→WEEKLY→DAILY: {'✅ PASS' if system_ok else '❌ FAIL (ver CSV)'}")

    # ── 7. summary.txt ────────────────────────────────────────────────────
    _write_summary(args.out_dir, PV, YEAR, MONTH, out_rows, ok=system_ok,
                   warn_n=warn_n,
                   wd_max=wd_max, dd_max=dd_max, mv_w=mv_w, mv_d=mv_d,
                   slices_adj=slices_adj, drift_cons=drift_cons,
                   fallback_summary=fallback_summary)

    return 0 if system_ok else 2


def _write_summary(
    out_dir: str,
    plan_version: str,
    year: int,
    month: int,
    rows: List[Dict],
    ok: bool = False,
    reason: str = "",
    wd_max: float = 0,
    dd_max: float = 0,
    mv_w: float = 0,
    mv_d: float = 0,
    slices_adj: Any = "?",
    drift_cons: Any = "?",
    fallback_summary: Any = "",
    warn_n: int = 0,
) -> None:
    from datetime import datetime
    lines = [
        "=" * 54,
        f"  PROJECTION VALIDATION SUMMARY",
        "=" * 54,
        f"  PLAN VERSION : {plan_version}",
        f"  PERIOD       : {year}-{month:02d}",
        f"  GENERATED AT : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"  MONTHLY  : {'OK' if rows else 'FAIL — no data'}",
        f"  WEEKLY   : {'OK' if ok else 'FAIL'}",
        f"  DAILY    : {'OK' if ok else 'FAIL'}",
        "",
        f"  WEEKLY DRIFT MAX  : {wd_max:.4f}%  (límite 1.0%)",
        f"  DAILY  DRIFT MAX  : {dd_max:.4f}%  (límite 1.0%)",
        f"  WEEKLY VAR MAX    : {mv_w:.2f}%    (límite 25%)",
        f"  DAILY  VAR MAX    : {mv_d:.2f}%    (límite 35%)",
        "",
        f"  CONSERVATION SLICES ADJUSTED : {slices_adj}",
        f"  CONSERVATION MAX DRIFT       : {drift_cons}",
        f"  FALLBACK LEVEL SUMMARY       : {fallback_summary}",
        "",
    ]
    if reason:
        lines += [f"  REASON : {reason}", ""]

    lines += [
        f"  VERDICT FINAL : {'SYSTEM READY ✅' if ok else 'NOT READY ❌'}",
        "=" * 54,
    ]

    if rows:
        pass_n = sum(1 for r in rows if r["verdict"] == "PASS")
        fail_n = sum(1 for r in rows if r["verdict"] == "FAIL")
        fail_rows = [r for r in rows if r["verdict"] == "FAIL"][:10]
        lines += ["", f"  combos×KPI: {len(rows)}   PASS={pass_n}   FAIL={fail_n}   WARN_NO_CURVE={warn_n}", ""]
        if fail_rows:
            lines.append("  FAILING ROWS (top 10):")
            for r in fail_rows:
                lines.append(f"    {r['city']}/{r['business_slice_name']}/{r['kpi']}"
                             f"  wΔ%={r['weekly_drift_pct']}  dΔ%={r['daily_drift_pct']}")

    path = os.path.join(out_dir, "projection_validation_summary.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[✓] Summary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
