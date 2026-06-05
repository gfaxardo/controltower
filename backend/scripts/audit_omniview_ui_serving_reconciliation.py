"""OMNI-COV-006 — UI/Serving Reconciliation Audit Script.

Read-only. Queries fact tables and serving for each metric x grain, compares
expected vs actual coverage. Detects gaps that would cause blank matrix cells.
"""
from __future__ import annotations
import argparse, json, sys, logging
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, '.')
from app.db.connection import get_db
from app.services.business_slice_service import FACT_DAILY, FACT_WEEKLY, FACT_MONTHLY

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

METRICS_BY_TABLE = {
    "daily": {
        "trips":   "trips_completed",
        "revenue": "revenue_yego_final",  # day_fact has _final
        "drivers": "active_drivers",
        "ticket":  "avg_ticket",
        "tpd":     "trips_per_driver",
    },
    "weekly": {
        "trips":   "trips_completed",
        "revenue": "revenue_yego_final",  # week_fact has _final
        "drivers": "active_drivers",
        "ticket":  "avg_ticket",
        "tpd":     "trips_per_driver",
    },
    "monthly": {
        "trips":   "trips_completed",
        "revenue": "revenue_yego_net",    # serving view only has _net
        "drivers": "active_drivers",
        "ticket":  "avg_ticket",
        "tpd":     "trips_per_driver",
    },
}

SERVING_TABLE = "serving.omniview_projection_daily_fact"

GRAINS = {
    "daily":   {"table": FACT_DAILY,    "period_col": "trip_date",   "period_fn": lambda d: d},
    "weekly":  {"table": FACT_WEEKLY,   "period_col": "week_start",  "period_fn": lambda d: d - timedelta(days=d.weekday())},
    "monthly": {"table": FACT_MONTHLY,  "period_col": "month",       "period_fn": lambda d: date(d.year, d.month, 1)},
}

def _closed_periods(grain: str, count: int) -> list[date]:
    today = date.today()
    out = []
    if grain == "daily":
        for i in range(1, count + 1):
            out.append(today - timedelta(days=i))
    elif grain == "weekly":
        mon = today - timedelta(days=today.weekday())
        for i in range(1, count + 1):
            out.append(mon - timedelta(weeks=i))
    elif grain == "monthly":
        ym = date(today.year, today.month, 1)
        for _ in range(count):
            if ym.month == 1:
                ym = date(ym.year - 1, 12, 1)
            else:
                ym = date(ym.year, ym.month - 1, 1)
            out.append(ym)
    return out

def run():
    results = []
    overall_pass = 0
    overall_warn = 0
    overall_fail = 0

    with get_db() as conn:
        cur = conn.cursor()

        for grain, gcfg in GRAINS.items():
            periods = _closed_periods(grain, 8)
            tbl = gcfg["table"]
            pcol = gcfg["period_col"]
            metrics = METRICS_BY_TABLE[grain]

            for mlabel, mcol in metrics.items():
                non_null = 0
                total_periods = 0
                missing = []

                for p in periods:
                    p_str = p.isoformat()
                    if grain == "daily":
                        cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {pcol} = %s::date AND {mcol} IS NOT NULL", (p_str,))
                    elif grain == "monthly":
                        cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {pcol} = %s::date AND {mcol} IS NOT NULL", (p_str,))
                    else:
                        cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {pcol} = %s::date AND {mcol} IS NOT NULL", (p_str,))
                    n = (cur.fetchone() or (0,))[0]
                    total_periods += 1
                    if n > 0:
                        non_null += 1
                    else:
                        missing.append(p_str)

                coverage_pct = round(100.0 * non_null / max(1, total_periods), 1)
                if coverage_pct >= 80:
                    status = "PASS"
                    overall_pass += 1
                elif coverage_pct >= 40:
                    status = "WARNING"
                    overall_warn += 1
                else:
                    status = "FAIL"
                    overall_fail += 1

                detail = f"{non_null}/{total_periods} periods with data ({coverage_pct}%)"
                if missing:
                    detail += f" missing: {missing[:3]}"
                    if len(missing) > 3:
                        detail += f" (+{len(missing)-3})"

                results.append({
                    "grain": grain,
                    "metric": mlabel,
                    "api_field": mcol,
                    "ui_kpi": mlabel,
                    "canonical_field": "revenue_yego_final" if mlabel == "revenue" else mcol,
                    "serving_has_data": non_null > 0,
                    "periods_with_data": non_null,
                    "periods_total": total_periods,
                    "coverage_pct": coverage_pct,
                    "missing_periods": missing,
                    "status": status,
                })

        # Confidence/trust data
        try:
            cur.execute("SELECT COUNT(*) FROM ops.omniview_matrix_trust_history")
            trust_n = cur.fetchone()[0]
            results.append({
                "grain": "all",
                "metric": "confidence",
                "api_field": "operational_decision.confidence.score",
                "ui_kpi": "trust",
                "serving_has_data": trust_n > 0,
                "coverage_pct": 100.0 if trust_n > 0 else 0.0,
                "status": "PASS" if trust_n > 0 else "FAIL",
            })
        except Exception:
            results.append({
                "grain": "all", "metric": "confidence", "status": "ERROR",
                "detail": "ops.omniview_matrix_trust_history not accessible"
            })
            overall_fail += 1

        cur.close()

    total = overall_pass + overall_warn + overall_fail
    verdict = "FAIL" if overall_fail > 0 else "WARNING" if overall_warn > 0 else "PASS"

    print("=" * 70)
    print("  UI/SERVING RECONCILIATION AUDIT")
    print(f"  {date.today().isoformat()}  |  {len(results)} checks")
    print("=" * 70)
    print()
    for r in results:
        tag = f"[{r['status']}]".ljust(9)
        g = r['grain'].ljust(8)
        m = r['metric'].ljust(10)
        extra = r.get('detail', f"{r.get('coverage_pct', 0)}% coverage")
        print(f"  {tag} {g} {m} {extra}")
    print()
    print(f"  PASS: {overall_pass}  WARNING: {overall_warn}  FAIL: {overall_fail}")
    print(f"  VERDICT: {verdict}")
    print()

    json_out = {"audit": "ui_serving_reconciliation", "date": date.today().isoformat(),
                 "verdict": verdict, "checks": results,
                 "summary": {"pass": overall_pass, "warning": overall_warn, "fail": overall_fail}}
    print(json.dumps(json_out, indent=2, default=str))

    return 1 if overall_fail > 0 else 0

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="OMNI-COV-006: UI/Serving Reconciliation")
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    if args.quiet:
        logging.disable(logging.CRITICAL)
    sys.exit(run())
