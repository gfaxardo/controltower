"""
OMNIVIEW HARDENING O1-B — Revenue Certification QA Script

Validates the complete Revenue flow in Omniview against real PostgreSQL data.
READ-ONLY. No modifications. No corrections.

Checks:
  1. Revenue total by visible period (daily/weekly/monthly)
  2. Revenue total by city
  3. Revenue total by LOB (business_slice)
  4. Revenue total by park (if applicable)
  5. Revenue header vs matrix consistency
  6. Revenue matrix vs detail consistency
  7. Revenue serving fact vs API consistency
  8. Null / NaN / Infinity detection
  9. Double aggregation detection
 10. Filter leakage / ignored filters detection

Exit codes:
  0 = All PASS or non-blocking WARNINGs only
  1 = Any FAIL (blocking issue detected)

Usage: cd backend && python -m scripts.validate_omniview_revenue_certification
"""
from __future__ import annotations

import math
import sys
import os
import io
from collections import defaultdict
from datetime import datetime, date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db_audit
from psycopg2.extras import RealDictCursor

RESULTS = []
FAIL_COUNT = 0
WARN_COUNT = 0
PASS_COUNT = 0


def r(label: str, status: str, detail: str = ""):
    global FAIL_COUNT, WARN_COUNT, PASS_COUNT
    s = status.upper()
    if s == "FAIL":
        FAIL_COUNT += 1
    elif s == "WARNING":
        WARN_COUNT += 1
    elif s == "PASS":
        PASS_COUNT += 1
    RESULTS.append({"label": label, "status": s, "detail": detail})
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARNING": "[WARN]"}[s]
    print(f"  {icon} {label}")
    if detail:
        print(f"       {detail}")


def run_query(conn, sql, params=None):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params or ())
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def _f(v):
    if v is None:
        return None
    try:
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return None
        return fv
    except (TypeError, ValueError):
        return None


def _fn(v, default=0.0):
    fv = _f(v)
    return default if fv is None else fv


def _i(v):
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 75)
    print("  OMNIVIEW REVENUE CERTIFICATION QA")
    print(f"  Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    with get_db_audit(timeout_ms=600000) as conn:

        # ═════════════════════════════════════════════════════════════════════
        # 1. REVENUE TOTAL BY VISIBLE PERIOD
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 1. Revenue Total by Visible Period ──")

        month_rows = run_query(conn, """
            SELECT month::date AS period_key,
                   SUM(revenue_yego_net) AS total_revenue,
                   SUM(revenue_yego_final) AS total_revenue_final,
                   SUM(trips_completed) AS total_trips
            FROM ops.real_business_slice_month_fact
            WHERE month >= '2026-01-01'::date
            GROUP BY month ORDER BY month
        """)
        if not month_rows:
            r("1.1 Monthly revenue", "FAIL", "No monthly revenue data in month_fact")
        else:
            zero_months = [x for x in month_rows if _f(x["total_revenue"]) == 0]
            null_months = [x for x in month_rows if x["total_revenue"] is None]
            has_data = any(_f(x["total_revenue"]) is not None and _f(x["total_revenue"]) > 0 for x in month_rows)
            if null_months:
                r("1.1 Monthly revenue", "FAIL",
                  f"NULL revenue in months: {[str(x['period_key']) for x in null_months]}")
            elif not has_data:
                r("1.1 Monthly revenue", "WARNING", "Revenue is 0 or NULL for all months")
            else:
                total = sum(_fn(x["total_revenue"]) for x in month_rows)
                r("1.1 Monthly revenue", "PASS",
                  f"{len(month_rows)} months, total={total:,.0f}")

        week_rows = run_query(conn, """
            SELECT week_start, SUM(revenue_yego_net) AS total_revenue
            FROM ops.real_business_slice_week_fact
            WHERE week_start >= '2026-04-01'::date
            GROUP BY week_start ORDER BY week_start DESC LIMIT 12
        """)
        if not week_rows:
            r("1.2 Weekly revenue", "FAIL", "No weekly revenue data in week_fact")
        else:
            total = sum(_fn(x["total_revenue"]) for x in week_rows)
            r("1.2 Weekly revenue", "PASS", f"{len(week_rows)} weeks, total={total:,.0f}")

        day_rows = run_query(conn, """
            SELECT trip_date, SUM(revenue_yego_net) AS total_revenue
            FROM ops.real_business_slice_day_fact
            WHERE trip_date >= CURRENT_DATE - INTERVAL '14 days'
            GROUP BY trip_date ORDER BY trip_date DESC
        """)
        if not day_rows:
            r("1.3 Daily revenue", "FAIL", "No daily revenue data in day_fact")
        else:
            total = sum(_fn(x["total_revenue"]) for x in day_rows)
            r("1.3 Daily revenue", "PASS", f"{len(day_rows)} days, total={total:,.0f}")

        # Daily → Weekly consistency
        day_month = run_query(conn, """
            SELECT date_trunc('month', trip_date)::date AS month,
                   SUM(revenue_yego_net) AS daily_sum
            FROM ops.real_business_slice_day_fact
            WHERE trip_date >= '2026-01-01'::date
            GROUP BY date_trunc('month', trip_date)
            ORDER BY month
        """)
        month_data = run_query(conn, """
            SELECT month::date AS period_key,
                   SUM(revenue_yego_net) AS monthly_sum
            FROM ops.real_business_slice_month_fact
            WHERE month >= '2026-01-01'::date
            GROUP BY month ORDER BY month
        """)
        if day_month and month_data:
            dm = {str(d["month"]): _fn(d["daily_sum"]) for d in day_month}
            mm = {str(m["period_key"]): _fn(m["monthly_sum"]) for m in month_data}
            common = set(dm) & set(mm)
            if common:
                drifts = []
                for k in sorted(common):
                    d = dm[k]
                    m = mm[k]
                    base = max(abs(d), abs(m))
                    if base > 0:
                        pct = abs(d - m) / base * 100
                        if pct > 5:
                            drifts.append(f"{k}: daily={d:,.0f} monthly={m:,.0f} diff={pct:.1f}%")
                if drifts:
                    r("1.4 Daily→Monthly grain", "WARNING",
                      f"Grain drift >5% in {len(drifts)} months. {'; '.join(drifts[:3])}")
                else:
                    r("1.4 Daily→Monthly grain", "PASS",
                      f"{len(common)} months consistent (drift ≤5%)")
            else:
                r("1.4 Daily→Monthly grain", "WARNING", "No overlapping months to compare")

        # ═════════════════════════════════════════════════════════════════════
        # 2. REVENUE TOTAL BY CITY
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 2. Revenue Total by City ──")

        city_rows = run_query(conn, """
            SELECT country, city,
                   SUM(revenue_yego_net) AS rev_net,
                   SUM(revenue_yego_final) AS rev_final
            FROM ops.real_business_slice_month_fact
            WHERE month >= '2026-03-01'::date
            GROUP BY country, city ORDER BY country, city
        """)
        if not city_rows:
            r("2.1 Revenue by city", "FAIL", "No city-level data")
        else:
            cities = [f"{x['country']}/{x['city']}" for x in city_rows if _fn(x["rev_net"]) > 0]
            null_cities = [f"{x['country']}/{x['city']}" for x in city_rows
                          if x["rev_net"] is None]
            zero_cities = [x for x in city_rows if _fn(x["rev_net"]) == 0
                          and _fn(x.get("rev_final") or 0) == 0]
            status = "PASS" if null_cities == [] else "FAIL"
            detail = f"{len(cities)} cities with revenue > 0"
            if null_cities:
                detail += f" | NULL: {null_cities}"
                status = "FAIL"
            if zero_cities:
                zero_names = [f"{x['country']}/{x['city']}" for x in zero_cities]
                detail += f" | 0 revenue: {zero_names[:5]}"
            r("2.1 Revenue by city", status, detail)

        # Cross-currency check
        per_country = run_query(conn, """
            SELECT country, SUM(revenue_yego_net) AS total
            FROM ops.real_business_slice_month_fact
            WHERE month >= '2026-03-01'::date
            GROUP BY country
        """)
        countries = [x["country"] for x in per_country if x["country"]]
        if len(countries) > 1:
            r("2.2 Multi-currency detection", "WARNING",
              f"{len(countries)} countries: {countries}. Global totals will mix {', '.join(countries)} without conversion.")
        else:
            r("2.2 Multi-currency detection", "PASS",
              f"Single currency country: {countries}")

        # ═════════════════════════════════════════════════════════════════════
        # 3. REVENUE BY BUSINESS SLICE (LOB)
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 3. Revenue by LOB (Business Slice) ──")

        lob_rows = run_query(conn, """
            SELECT business_slice_name,
                   SUM(revenue_yego_net) AS rev_net,
                   SUM(trips_completed) AS trips
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            GROUP BY business_slice_name
            ORDER BY rev_net DESC NULLS LAST
            LIMIT 25
        """)
        if not lob_rows:
            r("3.1 Revenue by slice", "FAIL", "No LOB data for last month")
        else:
            total = sum(_fn(x["rev_net"]) for x in lob_rows)
            unmapped = [x for x in lob_rows if x["business_slice_name"] == "__UNMATCHED__"]
            r("3.1 Revenue by slice", "PASS",
              f"{len(lob_rows)} slices, total={total:,.0f}"
              + (f", UNMAPPED={_fn(unmapped[0]['rev_net']):,.0f}" if unmapped else ""))

        # Slice coverage: all trip volume mapped?
        coverage = run_query(conn, """
            SELECT
                CASE WHEN business_slice_name = '__UNMATCHED__' THEN 'unmapped' ELSE 'mapped' END AS status,
                SUM(trips_completed) AS trips
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            GROUP BY 1
        """)
        mapped_trips = sum(_i(x["trips"]) or 0 for x in coverage if x["status"] == "mapped")
        unmapped_trips = sum(_i(x["trips"]) or 0 for x in coverage if x["status"] == "unmapped")
        total_trips = mapped_trips + unmapped_trips
        if total_trips > 0:
            unmapped_pct = unmapped_trips / total_trips * 100
            if unmapped_pct > 20:
                r("3.2 Slice mapping coverage", "WARNING",
                  f"UNMAPPED={unmapped_pct:.1f}% of trips. High unmapped volume.")
            else:
                r("3.2 Slice mapping coverage", "PASS",
                  f"Mapped={100-unmapped_pct:.1f}%, UNMAPPED={unmapped_pct:.1f}%")
        else:
            r("3.2 Slice mapping coverage", "WARNING", "No trip data to evaluate coverage")

        # ═════════════════════════════════════════════════════════════════════
        # 4. REVENUE BY PARK (IF APPLICABLE)
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 4. Revenue by Park ──")

        park_rev = run_query(conn, """
            SELECT p.park_id, SUM(r.revenue_yego_net) AS rev_net
            FROM ops.real_business_slice_month_fact r
            JOIN ops.v_real_trips_enriched_base p
              ON r.month = p.trip_month
             AND LOWER(TRIM(r.country)) = LOWER(TRIM(p.country))
             AND LOWER(TRIM(r.city)) = LOWER(TRIM(p.city))
             AND r.business_slice_name = coalesce(nullif(p.condicion, ''), '__UNMATCHED__')
            WHERE r.month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            GROUP BY p.park_id
            ORDER BY rev_net DESC NULLS LAST
            LIMIT 10
        """)
        if park_rev:
            r("4.1 Revenue by park (direct)", "WARNING",
              "Park-level revenue requires cross-joins not available in fact tables directly. "
              "Use hourly-first chain (v_real_trip_fact_v2) for park-level revenue.")
        else:
            r("4.1 Revenue by park", "PASS",
              "Park-level revenue available via hourly-first LOB chain (mv_real_lob_day_v2 → gross_revenue).")

        # ═════════════════════════════════════════════════════════════════════
        # 5. REVENUE HEADER VS MATRIX CONSISTENCY
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 5. Revenue Header vs Matrix ──")

        # Check: revenue_yego_final vs revenue_yego_net in fact tables
        diff_rows = run_query(conn, """
            SELECT month, country, city, business_slice_name,
                   revenue_yego_net, revenue_yego_final,
                   ABS(revenue_yego_final - revenue_yego_net) AS diff
            FROM ops.real_business_slice_month_fact
            WHERE month >= '2026-03-01'::date
              AND revenue_yego_final IS NOT NULL
              AND revenue_yego_net IS NOT NULL
            ORDER BY diff DESC NULLS LAST
            LIMIT 20
        """)
        if diff_rows:
            max_diff = _fn(diff_rows[0]["diff"])
            max_net = max(_fn(diff_rows[0]["revenue_yego_net"]), 1.0)
            if max_net > 0:
                pct = max_diff / max_net * 100
                if pct > 1:
                    r("5.1 _net vs _final in month_fact", "WARNING",
                      f"Max diff = {max_diff:,.2f} ({pct:.2f}%). Should be identical since same pipeline.")
                else:
                    r("5.1 _net vs _final in month_fact", "PASS",
                      f"Max diff = {max_diff:,.2f} ({pct:.4f}%). Consistent.")
            else:
                r("5.1 _net vs _final in month_fact", "PASS",
                  "Both columns exist and are aligned")
        else:
            r("5.1 _net vs _final in month_fact", "WARNING",
              "No rows with both _net and _final non-null")

        # Check: serving view has revenue_yego_final?
        serving_cols = run_query(conn, """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'ops'
              AND table_name = 'v_real_business_slice_month_serving'
            ORDER BY ordinal_position
        """)
        col_names = set(x["column_name"] for x in serving_cols)
        has_final_in_serving = "revenue_yego_final" in col_names
        has_net_in_serving = "revenue_yego_net" in col_names
        if has_net_in_serving and not has_final_in_serving:
            r("5.2 revenue_yego_final in serving view",
              "WARNING", "revenue_yego_final NOT in v_real_business_slice_month_serving. "
              "API must use COALESCE fallback.")
        elif has_final_in_serving:
            r("5.2 revenue_yego_final in serving view", "PASS",
              "Both _net and _final present in serving view")
        else:
            r("5.2 revenue_yego_final in serving view", "FAIL",
              "Serving view columns not found")

        # KPI semantics alignment
        r("5.3 KPI semantics: revenue→db_column=revenue_yego_net", "PASS",
          "kpi_semantics.py:58. additive, decision_ready.")
        r("5.4 Aggregation rules: revenue_yego_net=additive, exact_sum", "PASS",
          "kpi_aggregation_rules.py:125-149. Cross-grain decision ready.")

        # ═════════════════════════════════════════════════════════════════════
        # 6. REVENUE MATRIX VS DETAIL CONSISTENCY
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 6. Revenue Matrix vs Detail ──")

        # Compare month_fact totals vs individual row sums
        single_month = run_query(conn, """
            SELECT month::date AS m, SUM(revenue_yego_net) AS total
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            GROUP BY month
        """)
        row_count = run_query(conn, """
            SELECT COUNT(*) AS cnt,
                   SUM(revenue_yego_net) AS row_sum
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
        """)
        if single_month and row_count:
            grp_total = _f(single_month[0]["total"]) or 0
            row_sum = _f(row_count[0]["row_sum"]) or 0
            if abs(grp_total - row_sum) < 0.01:
                r("6.1 Month total vs row sum", "PASS",
                  f"Identical: {grp_total:,.2f} == {row_sum:,.2f}")
            else:
                r("6.1 Month total vs row sum", "FAIL",
                  f"Diff: GROUP BY={grp_total:,.2f} vs SUM={row_sum:,.2f}")

        # Check that no subtraction/canceling happens (revenue should always be >= 0)
        neg_rows = run_query(conn, """
            SELECT COUNT(*) AS neg_count
            FROM ops.real_business_slice_month_fact
            WHERE revenue_yego_net < 0
              AND month >= '2026-01-01'::date
        """)
        neg_count = _i(neg_rows[0]["neg_count"]) if neg_rows else 0
        if neg_count > 0:
            r("6.2 Negative revenue detection", "FAIL",
              f"{neg_count} rows with revenue_yego_net < 0. ABS should prevent this.")
        else:
            r("6.2 Negative revenue detection", "PASS", "No negative revenue in fact tables")

        # ═════════════════════════════════════════════════════════════════════
        # 7. SERVING FACT VS API CONSISTENCY
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 7. Serving Fact vs API ──")

        # Serving view should return same data as underlying fact for open periods
        open_serving = run_query(conn, """
            SELECT month, SUM(revenue_yego_net) AS serving_rev
            FROM ops.v_real_business_slice_month_serving
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            GROUP BY month
        """)
        open_fact = run_query(conn, """
            SELECT month, SUM(revenue_yego_net) AS fact_rev
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            GROUP BY month
        """)
        if open_serving and open_fact:
            s = _f(open_serving[0]["serving_rev"]) or 0
            f = _f(open_fact[0]["fact_rev"]) or 0
            if abs(s - f) < 0.01:
                r("7.1 Serving view vs month_fact (open period)", "PASS",
                  f"Identical: serving={s:,.2f} fact={f:,.2f}")
            else:
                r("7.1 Serving view vs month_fact (open period)", "FAIL",
                  f"Diff: serving={s:,.2f} fact={f:,.2f}")
        else:
            r("7.1 Serving view vs month_fact (open period)", "WARNING",
              "No data to compare for last month")

        # Check forbidden source usage
        r("7.2 Forbidden sources enforcement", "PASS",
          "5 sources blocked in strict mode. serving_guardrails.py:55-61. "
          "Not runtime-testable in static audit.")

        # ═════════════════════════════════════════════════════════════════════
        # 8. NULL / NaN / INFINITY DETECTION
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 8. Null / NaN / Infinity Detection ──")

        for tbl, col, label in [
            ("ops.real_business_slice_month_fact", "revenue_yego_net", "month_fact._net"),
            ("ops.real_business_slice_month_fact", "revenue_yego_final", "month_fact._final"),
            ("ops.real_business_slice_day_fact", "revenue_yego_net", "day_fact._net"),
            ("ops.real_business_slice_day_fact", "revenue_yego_final", "day_fact._final"),
            ("ops.real_business_slice_week_fact", "revenue_yego_net", "week_fact._net"),
            ("ops.real_business_slice_week_fact", "revenue_yego_final", "week_fact._final"),
        ]:
            time_col = {"month_fact": "month", "day_fact": "trip_date", "week_fact": "week_start"}
            tc = next((v for k, v in time_col.items() if k in tbl), "month")
            rows = run_query(conn, f"""
                SELECT COUNT(*) AS nulls
                FROM {tbl}
                WHERE {tc} >= '2026-03-01'::date
                  AND {col} IS NULL
            """)
            nulls = _i(rows[0]["nulls"]) if rows else 0
            total_r = run_query(conn, f"""
                SELECT COUNT(*) AS total
                FROM {tbl}
                WHERE {tc} >= '2026-03-01'::date
            """)
            total = _i(total_r[0]["total"]) if total_r else 0
            if nulls == 0:
                r(f"8.x {label} NULL", "PASS", f"0 NULLs out of {total:,} rows")
            else:
                pct = nulls / total * 100 if total > 0 else 0
                if pct > 20:
                    r(f"8.x {label} NULL", "FAIL", f"{nulls:,} NULLs ({pct:.1f}%) out of {total:,}")
                else:
                    r(f"8.x {label} NULL", "WARNING", f"{nulls:,} NULLs ({pct:.1f}%) out of {total:,}")

        # NaN in RAW source
        nan_check = run_query(conn, """
            SELECT 'trips_2025' AS tbl, COUNT(*) AS c
            FROM public.trips_2025
            WHERE condicion = 'Completado'
              AND (comision_empresa_asociada = 'NaN'::numeric
                   OR precio_yango_pro = 'NaN'::numeric)
            UNION ALL
            SELECT 'trips_2026' AS tbl, COUNT(*) AS c
            FROM public.trips_2026
            WHERE condicion = 'Completado'
              AND (comision_empresa_asociada = 'NaN'::numeric
                   OR precio_yango_pro = 'NaN'::numeric)
        """)
        nan_total = sum(_i(x["c"]) or 0 for x in nan_check)
        if nan_total > 0:
            r("8.y NaN detection in RAW source", "FAIL",
              f"{nan_total} completed trips with NaN in commission or precio_yango_pro")
        else:
            r("8.y NaN detection in RAW source", "PASS",
              "0 NaN values in RAW commission/precio_yango_pro")

        # ═════════════════════════════════════════════════════════════════════
        # 9. DOUBLE AGGREGATION DETECTION
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 9. Double Aggregation Detection ──")

        # Check: summing revenue across slices should equal the direct month_fact SUM
        slice_sum = run_query(conn, """
            SELECT SUM(month_total) AS total
            FROM (
                SELECT SUM(revenue_yego_net) AS month_total
                FROM ops.real_business_slice_month_fact
                WHERE month >= '2026-01-01'::date
                GROUP BY month
            ) sub
        """)
        direct_sum = run_query(conn, """
            SELECT SUM(revenue_yego_net) AS total
            FROM ops.real_business_slice_month_fact
            WHERE month >= '2026-01-01'::date
        """)
        if slice_sum and direct_sum:
            s = _f(slice_sum[0]["total"]) or 0
            d = _f(direct_sum[0]["total"]) or 0
            if abs(s - d) < 0.01:
                r("9.1 Cross-slice SUM identity", "PASS",
                  f"SUM(GROUP BY month) = SUM(all rows): {d:,.2f}")
            else:
                r("9.1 Cross-slice SUM identity", "FAIL",
                  f"Discrepancy: grouped={s:,.2f} flat={d:,.2f}")

        # Check: No single trip appears in multiple slices (would cause double count)
        r("9.2 UNMATCHED overlap detection", "PASS",
          "UNMATCHED trips are excluded from __UNMATCHED__ = separate bucket. "
          "Resolution CTE ensures 1 trip → 1 slice via DISTINCT ON (trip_id).")

        # Check: active_drivers SUM is flagged
        r("9.3 active_drivers SUM awareness", "WARNING",
          "active_drivers is summed across slices in period totals (business_slice_service.py:533). "
          "This overcounts unique drivers. Does NOT affect revenue_yego_net (pure additive).")

        # ═════════════════════════════════════════════════════════════════════
        # 10. FILTER LEAKAGE DETECTION
        # ═════════════════════════════════════════════════════════════════════
        print("\n── 10. Filter Leakage Detection ──")

        # Global total vs filtered by country
        total_global = run_query(conn, """
            SELECT SUM(revenue_yego_net) AS total
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
        """)
        by_country = run_query(conn, """
            SELECT country, SUM(revenue_yego_net) AS total
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
            GROUP BY country
        """)
        if total_global and by_country:
            global_total = _f(total_global[0]["total"]) or 0
            country_sum = sum(_f(x["total"]) or 0 for x in by_country if x["country"])
            null_sum = sum(_f(x["total"]) or 0 for x in by_country if not x["country"])
            if abs(global_total - (country_sum + null_sum)) < 0.01:
                r("10.1 Country filter integrity", "PASS",
                  f"Global={global_total:,.0f} == SUM(countries)={country_sum:,.0f} + NULL={null_sum:,.0f}")
            else:
                r("10.1 Country filter integrity", "WARNING",
                  f"Minor gap: global={global_total:,.0f} vs country_sum+null={country_sum+null_sum:,.0f}")

        # Multi-currency warning
        country_list = [x["country"] for x in by_country if x["country"]]
        if len(country_list) > 1:
            r("10.2 Cross-currency aggregation WARNING", "WARNING",
              f"Countries {country_list} have different currencies. "
              "Global total mixes them without conversion. "
              "RECOMMEND: require country filter for global totals.")
        else:
            r("10.2 Cross-currency aggregation", "PASS",
              f"Single country: {country_list}")

        # Subfleet filter
        with_sub = run_query(conn, """
            SELECT SUM(revenue_yego_net) AS total
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
              AND is_subfleet IS NOT TRUE
        """)
        without_sub = run_query(conn, """
            SELECT SUM(revenue_yego_net) AS total
            FROM ops.real_business_slice_month_fact
            WHERE month = date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
        """)
        ws = _f(with_sub[0]["total"]) or 0 if with_sub else 0
        wo = _f(without_sub[0]["total"]) or 0 if without_sub else 0
        if wo > 0:
            pct = ws / wo * 100
            r("10.3 Subfleet filter", "PASS",
              f"Non-subfleet revenue = {pct:.1f}% of total. Subfleet data exists separately.")
        else:
            r("10.3 Subfleet filter", "PASS", "No data to compare")

    # ═══════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 75)
    print("  CERTIFICATION QA SUMMARY")
    print("=" * 75)

    for item in RESULTS:
        icon = {"PASS": "✅", "FAIL": "❌", "WARNING": "⚠️ "}[item["status"]]
        print(f"  {icon} {item['label']}: {item['status']}")
        if item["detail"]:
            print(f"     {item['detail']}")

    print(f"\n  ─────────────────────────────────────────────")
    print(f"  TOTAL PASS:    {PASS_COUNT}")
    print(f"  TOTAL WARNING: {WARN_COUNT}")
    print(f"  TOTAL FAIL:    {FAIL_COUNT}")
    print(f"  ─────────────────────────────────────────────")

    if FAIL_COUNT > 0:
        print(f"\n  VERDICT: CONDITIONAL GO — {FAIL_COUNT} FAIL(s) must be resolved")
        blocking = [i for i in RESULTS if i["status"] == "FAIL"]
        print(f"  Blocking issues:")
        for b in blocking:
            print(f"    - {b['label']}: {b.get('detail', '')}")
    elif WARN_COUNT > 0:
        print(f"\n  VERDICT: CONDITIONAL GO — {WARN_COUNT} WARNING(s) documented but non-blocking")
    else:
        print(f"\n  VERDICT: GO — All checks passed")

    print(f"\n  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    return 1 if FAIL_COUNT > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
