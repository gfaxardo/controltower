"""
QA Script — Fase 1H.2K: TEMPORAL COMPARATIVES VALIDATION

Valida DoD/WoW/MoM restoration en Omniview Vs Proyeccion:
- daily: DoD (same weekday - 7 days)
- weekly: WoW (week_start - 7 days)
- monthly: MoM (month - 1)
"""
from __future__ import annotations

import os, sys, time, requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8000")
PLAN_VERSION = os.environ.get("CT_PLAN_VERSION", "ruta27_2026_04_21")
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[dict] = []
START_TIME = time.time()


def check(name, condition, detail="", warn=False):
    status = WARN if warn else (PASS if condition else FAIL)
    results.append({"check": name, "status": status, "detail": str(detail)})
    tag = f"[{status}]"
    msg = f"  {tag:7s} {name}"
    if detail and not condition:
        msg += f" -- {detail}"
    print(msg)


def main():
    global START_TIME
    START_TIME = time.time()
    print(f"=== QA 1H.2K Temporal Comparatives Validation ===")
    print(f"  BASE_URL={BASE_URL}")
    print(f"  PLAN_VERSION={PLAN_VERSION}")
    print()

    grains = [
        ("weekly", "WoW", 2026, None),
        ("daily", "DoD", 2026, 5),
        ("monthly", "MoM", 2026, None),
    ]

    for grain, label, year, month in grains:
        print(f"\n-- {grain.upper()} ({label}) --")
        params = {"plan_version": PLAN_VERSION, "grain": grain, "year": year}
        if month:
            params["month"] = month

        status, body = _get(
            "/ops/business-slice/omniview-projection", params=params, timeout=60
        )
        check(f"{grain}: API responds", status == 200, f"status={status}")
        if status != 200:
            continue

        rows = body.get("data", [])
        meta = body.get("meta", {})

        check(f"{grain}: served_from=fact", meta.get("served_from") == "fact",
              f"served_from={meta.get('served_from')}")
        check(f"{grain}: has rows", len(rows) > 0, f"rows={len(rows)}")

        # Check period_over_period metadata
        pop_meta = meta.get("period_over_period")
        check(f"{grain}: meta.period_over_period exists", pop_meta is not None,
              f"pop_meta={pop_meta}")
        check(f"{grain}: meta.period_over_period.kind={label.lower()}",
              pop_meta and pop_meta.get("kind") == label.lower(),
              f"kind={pop_meta.get('kind') if pop_meta else 'N/A'}")

        # Check rows have period_over_period field
        pop_rows = [r for r in rows if r.get("period_over_period")]
        check(f"{grain}: rows have period_over_period", len(pop_rows) > 0,
              f"pop_rows={len(pop_rows)} total={len(rows)}")

        # Check comparable rows (not first period)
        comparable = [r for r in pop_rows
                      if r["period_over_period"].get("comparable")]
        check(f"{grain}: has comparable PoP rows", len(comparable) > 0,
              f"comparable={len(comparable)}")

        # Sample a comparable row
        if comparable:
            sample = comparable[len(comparable) // 2]
            pop = sample["period_over_period"]
            check(f"{grain}: PoP has prev_period", pop.get("prev_period") is not None)
            check(f"{grain}: PoP has kind={label.lower()}",
                  pop.get("kind") == label.lower())

            # Check metrics for trips_completed
            trips_metric = pop.get("metrics", {}).get("trips_completed")
            if trips_metric:
                has_abs = trips_metric.get("abs") is not None
                has_pct = trips_metric.get("pct") is not None
                check(f"{grain}: trips_completed PoP has abs", has_abs)
                check(f"{grain}: trips_completed PoP has pct", has_pct)
                if has_abs:
                    cur = trips_metric.get("cur_real")
                    prev = trips_metric.get("prev_real")
                    print(f"         sample: cur={cur} prev={prev} abs={trips_metric['abs']} pct={trips_metric['pct']}%")

        # Cross-country check
        for c in ["peru", "colombia"]:
            p = dict(params)
            p["country"] = c
            s, b = _get("/ops/business-slice/omniview-projection", params=p, timeout=40)
            if s != 200:
                check(f"{grain} {c}: API responds", False, f"status={s}")
                continue
            crows = b.get("data", [])
            cpop = [r for r in crows if r.get("period_over_period")]
            check(f"{grain} {c}: has PoP rows", len(cpop) > 0,
                  f"pop_rows={len(cpop)} total={len(crows)}")

    _summary()


def _get(path, params=None, timeout=40):
    try:
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:500]
        return resp.status_code, body
    except Exception as e:
        return 0, str(e)[:300]


def _summary():
    elapsed = time.time() - START_TIME
    passed = sum(1 for r in results if r["status"] == PASS)
    failed = sum(1 for r in results if r["status"] == FAIL)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} PASS, {failed} FAIL ({elapsed:.1f}s)")
    if failed == 0:
        print("GO -- Temporal comparatives restored")
    else:
        print("NO-GO -- Temporal comparatives have failures")
    print(f"{'='*60}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
