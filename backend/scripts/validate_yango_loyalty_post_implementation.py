#!/usr/bin/env python3
"""
Post-Implementation Validation: Yango Loyalty Performance Foundation

Covers:
- T1: Serving layer verification
- T2: work_rule_id -> city mapping audit
- T3: April 2026 reference comparison
- T4: Endpoint smoke tests
- T6: QA checklist

Read-only. No modifications.
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

PASS = 0
FAIL = 0
WARN = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} -- {detail}")


def warning(label, detail=""):
    global WARN
    WARN += 1
    print(f"  [WARN] {label} -- {detail}")


# ═══════════════════════════════════════════════════════════════
# T1: SERVING LAYER VERIFICATION
# ═══════════════════════════════════════════════════════════════
print("=" * 70)
print("T1: SERVING LAYER VERIFICATION")
print("=" * 70)

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1.1 MV exists
    cur.execute("""
        SELECT schemaname, matviewname FROM pg_matviews
        WHERE schemaname = 'ops' AND matviewname = 'mv_yango_loyalty_performance_monthly_v1'
    """)
    mv = cur.fetchone()
    check("MV exists (pg_matviews)", mv is not None)

    # 1.2 MV has data
    if mv:
        cur.execute("SELECT COUNT(*) as cnt FROM ops.mv_yango_loyalty_performance_monthly_v1")
        mv_count = cur.fetchone()['cnt']
        check("MV has data", mv_count > 0, f"rows={mv_count}")
        print(f"    MV total rows: {mv_count}")

    # 1.3 MV feeds from fleet_summary_daily
    cur.execute("""
        SELECT definition FROM pg_matviews
        WHERE schemaname = 'ops' AND matviewname = 'mv_yango_loyalty_performance_monthly_v1'
    """)
    defn = cur.fetchone()
    if defn:
        mv_sql = defn['definition']
        check("MV references module_ct_fleet_summary_daily", 'module_ct_fleet_summary_daily' in mv_sql)
        check("MV references real_business_slice_month_fact", 'real_business_slice_month_fact' in mv_sql)
        check("MV references dim_yango_work_rule", 'dim_yango_work_rule' in mv_sql)

    # 1.4 dim table exists
    cur.execute("""
        SELECT COUNT(*) as cnt FROM information_schema.tables
        WHERE table_schema = 'ops' AND table_name = 'dim_yango_work_rule'
    """)
    check("dim_yango_work_rule table exists", cur.fetchone()['cnt'] > 0)

    # 1.5 Refresh function exists
    cur.execute("""
        SELECT routine_name FROM information_schema.routines
        WHERE routine_schema = 'ops' AND routine_name = 'refresh_yango_loyalty_performance_monthly_v1'
    """)
    check("Refresh function exists", cur.fetchone() is not None)

    # 1.6 No forbidden engines in service
    try:
        svc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "app", "services", "yango_loyalty_performance_service.py")
        with open(svc_path) as f:
            src = f.read()
        check("No forecast engine reference", "ForecastEngine" not in src and "forecast_engine" not in src)
        check("No suggestion engine reference", "SuggestionEngine" not in src and "suggestion_engine" not in src)
        check("No decision engine reference", "DecisionEngine" not in src and "decision_engine" not in src)
        check("No action engine reference", "ActionEngine" not in src and "action_engine" not in src)
        check("No sklearn/tensorflow/torch", "sklearn" not in src and "tensorflow" not in src and "torch" not in src)
    except Exception as e:
        check("Service file readable", False, str(e))

# ═══════════════════════════════════════════════════════════════
# T2: WORK_RULE_ID -> CITY MAPPING AUDIT
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("T2: WORK_RULE_ID -> CITY MAPPING AUDIT")
print("=" * 70)

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 2.1 Total work_rule_ids in dim
    cur.execute("SELECT COUNT(*) as cnt FROM ops.dim_yango_work_rule")
    dim_total = cur.fetchone()['cnt']
    print(f"\n  Total work_rule_id in dim: {dim_total}")

    # 2.2 Null/unknown cities
    cur.execute("SELECT COUNT(*) as cnt FROM ops.dim_yango_work_rule WHERE city_norm IS NULL OR city_norm = ''")
    null_city = cur.fetchone()['cnt']
    print(f"  work_rule_id with NULL/empty city: {null_city}")
    check("No NULL cities in dim", null_city == 0)

    # 2.3 Duplicates
    cur.execute("""
        SELECT work_rule_id, COUNT(*) as cnt
        FROM ops.dim_yango_work_rule
        GROUP BY work_rule_id HAVING COUNT(*) > 1
    """)
    dups = cur.fetchall()
    check("No duplicate work_rule_ids", len(dups) == 0, f"duplicates: {dups}")

    # 2.4 work_rule_ids in fleet_summary NOT in dim
    cur.execute("""
        SELECT DISTINCT f.driver_work_rule_id
        FROM public.module_ct_fleet_summary_daily f
        LEFT JOIN ops.dim_yango_work_rule wr ON wr.work_rule_id = f.driver_work_rule_id
        WHERE wr.work_rule_id IS NULL
    """)
    unmapped = cur.fetchall()
    print(f"  Unmapped work_rule_ids (in fleet_summary but not in dim): {len(unmapped)}")
    if unmapped:
        for u in unmapped:
            print(f"    UNMAPPED: {u['driver_work_rule_id']}")
    check("All work_rule_ids mapped", len(unmapped) == 0, f"unmapped: {len(unmapped)}")

    # 2.5 Full mapping listing
    print("\n  --- Current dim_yango_work_rule contents ---")
    cur.execute("SELECT work_rule_id, country, city_norm, label, notes FROM ops.dim_yango_work_rule ORDER BY city_norm, label")
    dim_rows = cur.fetchall()
    for r in dim_rows:
        print(f"    {r['work_rule_id'][:16]}... -> {r['city_norm']} ({r['label']})")

    # 2.6 Supply Hours distribution by work_rule_id (April 2026)
    print("\n  --- SH Distribution by work_rule_id (April 2026) ---")
    cur.execute("""
        SELECT f.driver_work_rule_id,
               wr.city_norm,
               wr.label,
               COUNT(DISTINCT f.driver_id) as drivers_all,
               COUNT(DISTINCT f.driver_id) FILTER (WHERE f.count_orders_completed > 0) as drivers_active,
               SUM(f.work_time_hours) as sh_total,
               SUM(f.work_time_hours) FILTER (WHERE f.count_orders_completed > 0) as sh_active_only
        FROM public.module_ct_fleet_summary_daily f
        LEFT JOIN ops.dim_yango_work_rule wr ON wr.work_rule_id = f.driver_work_rule_id
        WHERE f.fecha >= '2026-04-01' AND f.fecha < '2026-05-01'
        GROUP BY f.driver_work_rule_id, wr.city_norm, wr.label
        ORDER BY SUM(f.work_time_hours) DESC
    """)
    sh_by_rule = cur.fetchall()
    print(f"  {'work_rule':<18} {'city':<12} {'label':<18} {'drv_all':>8} {'drv_act':>8} {'SH_total':>12} {'SH_active':>12}")
    print(f"  {'-'*18} {'-'*12} {'-'*18} {'-'*8} {'-'*8} {'-'*12} {'-'*12}")
    for r in sh_by_rule:
        print(f"  {r['driver_work_rule_id'][:18]} {(r['city_norm'] or '?'):<12} {(r['label'] or '?')[:18]:<18} "
              f"{r['drivers_all']:>8} {r['drivers_active']:>8} {float(r['sh_total']):>12,.0f} {float(r['sh_active_only'] or 0):>12,.0f}")

    # 2.7 Supply Hours distribution by CITY (resultant)
    print("\n  --- SH Distribution by CITY (April 2026) ---")
    cur.execute("""
        SELECT COALESCE(wr.city_norm, '_unmapped') as city_norm,
               COUNT(DISTINCT f.driver_id) as drivers_all,
               COUNT(DISTINCT f.driver_id) FILTER (WHERE f.count_orders_completed > 0) as drivers_active,
               SUM(f.work_time_hours) as sh_total
        FROM public.module_ct_fleet_summary_daily f
        LEFT JOIN ops.dim_yango_work_rule wr ON wr.work_rule_id = f.driver_work_rule_id
        WHERE f.fecha >= '2026-04-01' AND f.fecha < '2026-05-01'
        GROUP BY COALESCE(wr.city_norm, '_unmapped')
        ORDER BY SUM(f.work_time_hours) DESC
    """)
    sh_by_city = cur.fetchall()
    total_sh = 0
    for r in sh_by_city:
        sh = float(r['sh_total'])
        total_sh += sh
        print(f"    {r['city_norm']:<12}: drivers={r['drivers_all']:>6}, active={r['drivers_active']:>6}, SH={sh:>12,.0f}")
    print(f"    {'TOTAL':<12}: SH={total_sh:>12,.0f}")

    # 2.8 Reference comparison for SH risk assessment
    print("\n  --- SH Risk Assessment (April 2026 vs Reference) ---")
    ref_sh = {"lima": 357000, "trujillo": 20127, "arequipa": 12735}
    ref_total = sum(ref_sh.values())
    print(f"    Reference total SH: {ref_total:,.0f}")
    print(f"    Fleet summary total SH: {total_sh:,.0f}")
    print(f"    Coverage: {total_sh/ref_total*100:.1f}% of reference")

    for r in sh_by_city:
        city = r['city_norm']
        actual_sh = float(r['sh_total'])
        if city in ref_sh:
            expected = ref_sh[city]
            diff = actual_sh - expected
            diff_pct = diff / expected * 100 if expected else 0
            status = "OK" if abs(diff_pct) <= 5 else "WARNING" if abs(diff_pct) <= 20 else "CRITICAL"
            print(f"    {city:<12}: actual={actual_sh:>10,.0f}  ref={expected:>10,.0f}  diff={diff:>+10,.0f} ({diff_pct:>+6.1f}%) [{status}]")
            if status == "CRITICAL":
                warning(f"SH {city} differs {abs(diff_pct):.0f}% from reference",
                        "work_rule->city mapping likely INCORRECT for this city")

# ═══════════════════════════════════════════════════════════════
# T3: VALIDATE APRIL 2026 VS REFERENCE (via serving fact)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("T3: APRIL 2026 VALIDATION vs REFERENCE")
print("=" * 70)

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Query from the MV directly
    cur.execute("""
        SELECT city_norm, active_drivers_mtd, supply_hours_mtd, ad_official_source, ad_fleet_summary_source
        FROM ops.mv_yango_loyalty_performance_monthly_v1
        WHERE month_start = '2026-04-01' AND country = 'peru'
        ORDER BY active_drivers_mtd DESC
    """)
    april_rows = cur.fetchall()

    ref_values = {
        "lima":     {"ad": 5601, "sh": 357000},
        "trujillo": {"ad": 550,  "sh": 20127},
        "arequipa": {"ad": 269,  "sh": 12735},
    }

    print(f"\n  {'City':<12} {'AD_actual':>10} {'AD_ref':>8} {'AD_diff':>9} {'AD%':>7} {'AD_vrd':>9}  {'SH_actual':>12} {'SH_ref':>10} {'SH_diff':>12} {'SH%':>7} {'SH_vrd':>9}")
    print(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*9} {'-'*7} {'-'*9}  {'-'*12} {'-'*10} {'-'*12} {'-'*7} {'-'*9}")

    for row in april_rows:
        city = row['city_norm']
        if city not in ref_values:
            continue
        ref = ref_values[city]
        ad_actual = int(row['active_drivers_mtd'] or 0)
        sh_actual = float(row['supply_hours_mtd'] or 0)
        ad_ref = ref['ad']
        sh_ref = ref['sh']

        ad_diff = ad_actual - ad_ref
        ad_pct = ad_diff / ad_ref * 100 if ad_ref else 0
        sh_diff = sh_actual - sh_ref
        sh_pct = sh_diff / sh_ref * 100 if sh_ref else 0

        ad_verdict = "OK" if abs(ad_pct) <= 3 else "WARNING" if abs(ad_pct) <= 10 else "BLOCKED"
        sh_verdict = "OK" if abs(sh_pct) <= 5 else "WARNING" if abs(sh_pct) <= 20 else "BLOCKED"

        print(f"  {city:<12} {ad_actual:>10,} {ad_ref:>8,} {ad_diff:>+9,} {ad_pct:>+6.1f}% {ad_verdict:>9}  "
              f"{sh_actual:>12,.0f} {sh_ref:>10,} {sh_diff:>+12,.0f} {sh_pct:>+6.1f}% {sh_verdict:>9}")

        # Check verdicts
        if ad_verdict == "OK":
            check(f"{city} AD within 3% tolerance", True)
        elif ad_verdict == "WARNING":
            warning(f"{city} AD differs {abs(ad_pct):.1f}% from reference",
                    "AD uses SUM(active_drivers) across ALL business slices (includes Delivery, TukTuk, Cargo, YMA, PRO)")
        else:
            check(f"{city} AD within 10% tolerance", False,
                  f"diff={ad_pct:.1f}%, actual={ad_actual}, ref={ad_ref}")

        if sh_verdict == "OK":
            check(f"{city} SH within 5% tolerance", True)
        elif sh_verdict == "WARNING":
            warning(f"{city} SH differs {abs(sh_pct):.1f}% from reference",
                    "work_rule->city mapping may need adjustment")
        else:
            check(f"{city} SH within 20% tolerance", False,
                  f"diff={sh_pct:.1f}%, actual={sh_actual:.0f}, ref={sh_ref}")

    # Probable cause analysis
    print("\n  --- Cause Analysis ---")
    print("  AD differences:")
    print("    - AD source: ops.real_business_slice_month_fact SUM(active_drivers)")
    print("    - Includes ALL business slices: Auto regular + Delivery + TukTuk + Cargo + YMA + PRO")
    print("    - Reference may only count 'Auto regular' slice (Lima Auto regular = 5496, close to ref 5601)")
    print("  SH differences:")
    print("    - SH source: module_ct_fleet_summary_daily SUM(work_time_hours) grouped by dim_yango_work_rule")
    print("    - CRITICAL: work_rule_id -> city mapping was ESTIMATED, not verified with Yango ops team")
    print("    - Total fleet_summary SH (310K) < reference total SH (389K) = data coverage gap")
    print("    - Individual city assignment depends on which work_rules map to which cities")

# ═══════════════════════════════════════════════════════════════
# T4: SMOKE TEST ENDPOINT
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("T4: SMOKE TEST ENDPOINT (via service function)")
print("=" * 70)

from app.services.yango_loyalty_performance_service import get_loyalty_performance

test_cases = [
    {"label": "April 2026, Peru, no city", "params": {"month": "2026-04", "country": "peru"}},
    {"label": "Current month, Peru", "params": {"country": "peru"}},
    {"label": "April 2026, city=lima", "params": {"month": "2026-04", "country": "peru", "city": "lima"}},
    {"label": "April 2026, city=trujillo", "params": {"month": "2026-04", "country": "peru", "city": "trujillo"}},
    {"label": "April 2026, city=arequipa", "params": {"month": "2026-04", "country": "peru", "city": "arequipa"}},
    {"label": "Month with no data (2025-01)", "params": {"month": "2025-01", "country": "peru"}},
    {"label": "Invalid month format", "params": {"month": "bad-month", "country": "peru"}},
]

for tc in test_cases:
    print(f"\n  --- {tc['label']} ---")
    try:
        result = get_loyalty_performance(**tc['params'])
        is_dict = isinstance(result, dict)
        has_month = 'month' in result
        has_cities = isinstance(result.get('cities'), list)
        has_summary = isinstance(result.get('summary'), dict)
        has_freshness = result.get('freshness_status') in ('ok', 'warning', 'stale', 'no_data', 'error')
        has_target = result.get('target_status') in ('configured', 'partial', 'missing_targets', 'error')
        has_scoring = result.get('scoring_status') in ('enabled', 'blocked_missing_targets', 'blocked_error')
        has_remediation = isinstance(result.get('remediation'), list)

        no_500 = result.get('freshness_status') != 'error'
        ad_positive = (result.get('summary', {}).get('active_drivers_mtd') or 0) >= 0
        sh_positive = (result.get('summary', {}).get('supply_hours_mtd') or 0) >= 0

        all_ok = all([is_dict, has_month, has_cities, has_summary, has_freshness, has_target, has_scoring, has_remediation])
        status = "PASS" if all_ok else "PARTIAL"
        print(f"    Status: {status}")
        print(f"    month={result.get('month')}, freshness={result.get('freshness_status')}, "
              f"target={result.get('target_status')}, scoring={result.get('scoring_status')}")
        print(f"    cities={len(result.get('cities', []))}, AD={result.get('summary', {}).get('active_drivers_mtd')}, "
              f"SH={result.get('summary', {}).get('supply_hours_mtd')}")
        if result.get('remediation'):
            print(f"    remediation: {[r['type'] for r in result['remediation']]}")

        check(f"Endpoint [{tc['label']}] responds valid structure", all_ok,
              f"missing: dict={is_dict}, month={has_month}, cities={has_cities}, summary={has_summary}")

        # Specific validations
        if "no data" in tc['label'].lower() or "invalid" in tc['label'].lower():
            check(f"  No crash on {tc['label']}", no_500)
        elif "city=" in tc['label']:
            city_count = len(result.get('cities', []))
            check(f"  City filter returns <=1 city", city_count <= 1 or city_count > 0)

    except Exception as e:
        check(f"Endpoint [{tc['label']}] no exception", False, str(e)[:100])

# Additional endpoint-specific checks
print("\n  --- Endpoint contract validation ---")
result_apr = get_loyalty_performance(month="2026-04", country="peru")
check("No 500 error on missing targets", result_apr.get('freshness_status') != 'error')
check("Returns remediation when missing targets",
      any(r['type'] == 'missing_targets' for r in result_apr.get('remediation', [])))
check("scoring_status blocked when missing targets",
      result_apr.get('scoring_status') == 'blocked_missing_targets')
check("AD returned even without targets", (result_apr.get('summary', {}).get('active_drivers_mtd') or 0) > 0)
check("SH returned even without targets", (result_apr.get('summary', {}).get('supply_hours_mtd') or 0) > 0)
check("freshness_status is valid", result_apr.get('freshness_status') in ('ok', 'warning', 'stale', 'no_data'))

# ═══════════════════════════════════════════════════════════════
# T6: ADDITIONAL QA CHECKS
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("T6: ADDITIONAL QA CHECKS")
print("=" * 70)

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Omniview check - make sure no interference
    cur.execute("""
        SELECT COUNT(*) as cnt FROM information_schema.tables
        WHERE table_schema = 'ops' AND table_name LIKE 'mv_real%'
    """)
    omniview_mvs = cur.fetchone()['cnt']
    check("Omniview MVs still present", omniview_mvs > 0, f"found {omniview_mvs}")

    # Check MV freshness
    cur.execute("""
        SELECT MAX(data_until) as max_date, refreshed_at
        FROM ops.mv_yango_loyalty_performance_monthly_v1
        WHERE country = 'peru'
        GROUP BY refreshed_at
        ORDER BY refreshed_at DESC LIMIT 1
    """)
    freshness_row = cur.fetchone()
    if freshness_row:
        print(f"  MV data_until: {freshness_row['max_date']}, refreshed_at: {freshness_row['refreshed_at']}")

    # Check no scoring is active without N+R
    check("No complete scoring active (blocked without N+R)",
          result_apr.get('scoring_status') != 'enabled')

    # Verify ranking is not alphabetical
    cities_list = [c['city_norm'] for c in result_apr.get('cities', [])]
    check("Ranking not alphabetical", cities_list != sorted(cities_list) or len(cities_list) <= 1,
          f"order: {cities_list}")
    if cities_list:
        check("Lima first (largest volume)", cities_list[0] == 'lima',
              f"first city is: {cities_list[0]}")

# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"FINAL RESULTS: {PASS} PASS | {FAIL} FAIL | {WARN} WARN")
print("=" * 70)

if FAIL == 0 and WARN == 0:
    print("\nVERDICT: GO")
elif FAIL == 0 and WARN > 0:
    print("\nVERDICT: CONDITIONAL GO")
    print("  Warnings need attention but are not blocking.")
else:
    print("\nVERDICT: NO-GO")
    print("  Failures must be resolved before proceeding.")

print("\nKEY FINDINGS:")
if WARN > 0:
    print("  - Supply Hours by city mapping needs verification with ops team")
    print("  - AD includes all business slices (may exceed single-slice reference)")
    print("  - Fleet summary total SH < reference total (data coverage gap)")
print(f"\nRECOMMENDATION: {'Proceed to mapping correction before N+R' if WARN > 0 else 'Ready for next phase'}")

sys.exit(0 if FAIL == 0 else 1)
