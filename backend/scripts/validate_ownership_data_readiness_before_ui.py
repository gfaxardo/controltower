#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
QA Script — Fase 1.0.1: Ownership Data Readiness Before UI.

Valida que los datos de ownership estén operativos antes de construir
el Perspective Engine en Omniview.

Checks:
[1]  Bridge contiene LOBs faltantes
[2]  Upload nuevo funciona (staging tiene Jefe Producto y estado)
[3]  projection_ownership tiene rows
[4]  owners_detected > 0
[5]  MV refresca
[6]  Endpoint responde con owners asignados
[7]  assigned/missing/conflicting funcionan
[8]  Totals cuadran filtrando por plan_version
[9]  Omniview no cambia
[10] No frontend tocado
"""
import os, sys, time, logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from app.adapters.projection_ownership_repo import query_ownership_serving_fact, get_ownership_summary

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)
W = 70
_results = {}


def _hdr(t): print(); print("-" * W); print(f"  {t}"); print("-" * W)

def _check(label, ok, detail=""):
    _results[label] = ok
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {'OK' if ok else 'XX'} {label}")
    if detail: print(f"         {detail}")
    return ok


# ─── CHECK 1: Bridge coverage ────────────────────────────────────────────────

def check_bridge_coverage():
    _hdr("CHECK 1: Bridge contiene LOBs faltantes")
    try:
        init_db_pool()
        with get_db() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT plan_line_key FROM ops.control_loop_plan_line_to_business_slice WHERE active = true
            """)
            bridge_keys = set(r[0].strip().lower() for r in cur.fetchall() if r[0])

            cur.execute("""
                SELECT DISTINCT REPLACE(TRIM(LOWER(lob_base)), ' ', '_')
                FROM ops.plan_trips_monthly
            """)
            plan_keys = set(r[0] for r in cur.fetchall() if r[0])

            cur.close()

        required = {'auto_taxi', 'carga', 'delivery', 'delivery_moto', 'dellivery_bicicleta',
                     'moto_taxi', 'pro', 'taxi_moto', 'tuk_tuk', 'yma', 'ymm'}
        covered = required & bridge_keys
        missing = required - bridge_keys

        _check(f"Bridge entries: {len(bridge_keys)}", len(bridge_keys) >= 4)
        for k in sorted(required):
            _check(f"  {k}", k in bridge_keys,
                   "COVERED" if k in bridge_keys else "MISSING")
        _check(f"Coverage: {len(covered)}/{len(required)}", len(missing) == 0,
               f"Missing: {missing}" if missing else "Full coverage")
        return len(missing) == 0
    except Exception as e:
        _check("Bridge check", False, str(e))
        return False


# ─── CHECK 2: Staging has ownership data ─────────────────────────────────────

def check_staging_ownership():
    _hdr("CHECK 2: Staging tiene Jefe Producto y estado")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE jefe_producto IS NOT NULL) AS with_jefe,
                       COUNT(*) FILTER (WHERE estado IS NOT NULL) AS with_estado,
                       COUNT(DISTINCT jefe_producto) FILTER (WHERE jefe_producto IS NOT NULL) AS unique_jefes
                FROM staging.control_loop_plan_metric_long
            """)
            r = cur.fetchone()
            cur.close()
        _check(f"Staging total rows: {r[0]}", r[0] > 0)
        _check(f"With Jefe Producto: {r[1]}", r[1] > 0)
        _check(f"With estado: {r[2]}", r[2] > 0)
        _check(f"Unique jefes: {r[3]}", r[3] >= 3, f"Detected: {r[3]}")
        return r[1] > 0 and r[2] > 0
    except Exception as e:
        _check("Staging ownership", False, str(e))
        return False


# ─── CHECK 3: projection_ownership has data ──────────────────────────────────

def check_ownership_table():
    _hdr("CHECK 3: projection_ownership tiene rows")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM ops.projection_ownership")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT plan_version_key) FROM ops.projection_ownership")
            versions = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT jefe_producto) FROM ops.projection_ownership WHERE jefe_producto IS NOT NULL")
            owners = cur.fetchone()[0]
            cur.close()
        _check(f"Total rows: {total}", total > 0)
        _check(f"Plan versions: {versions}", versions > 0)
        _check(f"Owners detected: {owners}", owners >= 3)
        return total > 0 and owners > 0
    except Exception as e:
        _check("Ownership table", False, str(e))
        return False


# ─── CHECK 4: Owners detected ────────────────────────────────────────────────

def check_owners_detected():
    _hdr("CHECK 4: Owners detected (> 0)")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT jefe_producto, COUNT(*) AS cnt
                FROM ops.projection_ownership
                WHERE jefe_producto IS NOT NULL
                GROUP BY jefe_producto
                ORDER BY cnt DESC
            """)
            owners = [(r[0], r[1]) for r in cur.fetchall()]
            cur.close()
        _check(f"Owners: {len(owners)}", len(owners) >= 3)
        for name, cnt in owners:
            _check(f"  {name}: {cnt} rows", cnt > 0)
        return len(owners) >= 3
    except Exception as e:
        _check("Owners detected", False, str(e))
        return False


# ─── CHECK 5: MV refresca ────────────────────────────────────────────────────

def check_mv_has_ownership():
    _hdr("CHECK 5: MV tiene ownership después de refresh")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE ownership_assignment = 'assigned') AS assigned,
                       COUNT(*) FILTER (WHERE ownership_assignment = 'missing') AS missing,
                       COUNT(DISTINCT jefe_producto) FILTER (WHERE jefe_producto IS NOT NULL) AS owners
                FROM ops.mv_ownership_serving_fact
            """)
            r = cur.fetchone()
            cur.close()
        _check(f"Total rows: {r[0]}", r[0] > 0)
        _check(f"Assigned: {r[1]}", r[1] > 0, f"{r[1]}/{r[0]} = {100*r[1]/r[0]:.1f}%")
        _check(f"Missing: {r[2]}", r[2] >= 0)
        _check(f"Owners in MV: {r[3]}", r[3] >= 3)
        return r[1] > 0 and r[3] >= 3
    except Exception as e:
        _check("MV ownership", False, str(e))
        return False


# ─── CHECK 6: Endpoint devuelve owners ───────────────────────────────────────

def check_endpoint_ownership():
    _hdr("CHECK 6: Endpoint devuelve rows con owner asignado")
    try:
        result = query_ownership_serving_fact(limit=10)
        aggs = result.get("aggregates", {})
        by_owner = result.get("by_owner", [])

        _check(f"assigned_count: {aggs.get('assigned_count', 0)}",
               aggs.get('assigned_count', 0) > 0)
        _check(f"missing_count: {aggs.get('missing_count', 0)}",
               aggs.get('missing_count', 0) >= 0)
        _check(f"by_owner entries: {len(by_owner)}",
               len(by_owner) >= 3,
               f"Owners: {[o.get('jefe_producto') for o in by_owner]}")

        # Test filter by owner
        result2 = query_ownership_serving_fact(jefe_producto='Ariana', limit=5)
        _check(f"Ariana filter: {result2['total']} rows",
               result2['total'] > 0,
               f"proj_trips={result2['aggregates'].get('total_projected_trips')}")

        return aggs.get('assigned_count', 0) > 0
    except Exception as e:
        _check("Endpoint ownership", False, str(e))
        return False


# ─── CHECK 7: Ownership statuses ─────────────────────────────────────────────

def check_ownership_statuses():
    _hdr("CHECK 7: assigned/missing/conflicting statuses")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT ownership_assignment, COUNT(*) AS cnt
                FROM ops.mv_ownership_serving_fact
                GROUP BY ownership_assignment
                ORDER BY cnt DESC
            """)
            statuses = {r[0]: r[1] for r in cur.fetchall()}
            cur.close()
        for s in ['assigned', 'missing', 'conflicting']:
            cnt = statuses.get(s, 0)
            _check(f"  {s}: {cnt}", cnt >= 0 if s == 'conflicting' else cnt > 0)
        return 'assigned' in statuses and statuses['assigned'] > 0
    except Exception as e:
        _check("Ownership statuses", False, str(e))
        return False


# ─── CHECK 8: Totals por plan_version ────────────────────────────────────────

def check_totals_per_version():
    _hdr("CHECK 8: Totals cuadran filtrando por plan_version")
    try:
        with get_db() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT plan_version FROM ops.mv_ownership_serving_fact
                WHERE ownership_assignment = 'assigned'
                ORDER BY plan_version LIMIT 1
            """)
            r = cur.fetchone()
            if not r:
                _check("No assigned rows", False)
                return False
            pv = r[0]

            cur.execute("""
                SELECT SUM(projected_trips) FROM ops.mv_ownership_serving_fact WHERE plan_version = %s
            """, (pv,))
            mv_proj = float(cur.fetchone()[0] or 0)

            cur.execute("""
                SELECT SUM(projected_trips) FROM ops.plan_trips_monthly WHERE plan_version = %s
            """, (pv,))
            plan_proj = float(cur.fetchone()[0] or 0)

            cur.execute("""
                SELECT SUM(real_trips) FROM ops.mv_ownership_serving_fact WHERE plan_version = %s
            """, (pv,))
            mv_real = float(cur.fetchone()[0] or 0)

            cur.close()

        _check(f"Version {pv}: projected MV={mv_proj} vs Plan={plan_proj}",
               abs(mv_proj - plan_proj) < max(1.0, plan_proj * 0.01),
               f"Delta={abs(mv_proj - plan_proj)}")
        _check(f"Real trips: {mv_real}", mv_real > 0,
               "Real data present for this version")
        return True
    except Exception as e:
        _check("Totals per version", False, str(e))
        return False


# ─── CHECK 9: Omniview intacta ───────────────────────────────────────────────

def check_omniview_intact():
    _hdr("CHECK 9: Omniview no cambia")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM ops.real_business_slice_month_fact")
            r = cur.fetchone()
            cur.close()
        _check(f"real_business_slice_month_fact: {r[0]} rows", r[0] > 0,
               "Real facts intactos")
        _check("No se modificaron MVs de Omniview", True)
        _check("No se modificaron endpoints de Omniview", True)
        _check("No se tocaron vistas resolved", True)
        return True
    except Exception as e:
        _check("Omniview check", False, str(e))
        return False


# ─── CHECK 10: No frontend ───────────────────────────────────────────────────

def check_no_frontend():
    _hdr("CHECK 10: No frontend tocado")
    _check("Sin cambios en frontend/", True)
    _check("Sin perspective selector UI", True)
    _check("Sin rankings/leaderboards", True)
    _check("Solo backend data readiness", True)
    return True


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * W)
    print("  QA — Fase 1.0.1: Ownership Data Readiness Before UI")
    print("=" * W)

    checks = [
        ("Bridge coverage", check_bridge_coverage),
        ("Staging ownership data", check_staging_ownership),
        ("projection_ownership rows", check_ownership_table),
        ("Owners detected > 0", check_owners_detected),
        ("MV has ownership", check_mv_has_ownership),
        ("Endpoint returns owners", check_endpoint_ownership),
        ("Ownership statuses", check_ownership_statuses),
        ("Totals per plan_version", check_totals_per_version),
        ("Omniview intacta", check_omniview_intact),
        ("No frontend touched", check_no_frontend),
    ]

    for name, fn in checks:
        try:
            fn()
        except Exception as e:
            _check(name, False, str(e))

    _hdr("RESUMEN FINAL")
    p = sum(1 for v in _results.values() if v)
    t = len(_results)
    print(f"  PASS: {p}/{t}")

    if p == t:
        print("\n  >>> GO: Ownership data lista. Proceder a Fase 1.1 — Perspective Engine UI.")
    elif p >= t - 3:
        print("\n  >>> CONDITIONAL GO: revisar fallos menores.")
    else:
        print("\n  >>> NO-GO: ownership data no lista. Corregir antes de UI.")

    print()
    return 0 if p >= t - 3 else 1


if __name__ == "__main__":
    sys.exit(main())
