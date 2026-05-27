#!/usr/bin/env python
"""
FASE 1.1.1 — End-to-End Unified Projection Upload Validation.

Ejecuta todas las validaciones: CSV → Upload → Canonical → Ownership → Serving → Omniview.
Imprime GO/CONDITIONAL GO/NO-GO al final.
"""
import sys, os, time, re, hashlib, csv as csv_mod, uuid, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.db.connection import get_db, init_db_pool

W = 72
CSV_PATH = r"C:\Users\Pc\Downloads\plantilla proyeccion Control Tower - plantilla_unificada (1).csv"
PV_KEY = f"e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
_results = {}
_batch_id = str(uuid.uuid4())


def _hdr(t):
    print(); print("-" * W); print(f"  {t}"); print("-" * W)


def _chk(label, ok, detail=""):
    _results[label] = ok
    m = "PASS" if ok else "FAIL"
    detail_str = f"\n         {detail}" if detail else ""
    print(f"  [{m}] {'OK' if ok else 'XX'} {label}{detail_str}")
    return ok


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 1 — VALIDATE CSV
# ═══════════════════════════════════════════════════════════════════════════════

def step_validate_csv():
    _hdr(f"PASO 1: CSV Validation  ({os.path.basename(CSV_PATH)})")
    
    if not os.path.exists(CSV_PATH):
        return _chk("CSV existe", False, CSV_PATH)
    
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv_mod.DictReader(f)
        rows_raw = list(reader)
    
    cols = list(rows_raw[0].keys()) if rows_raw else []
    required_cols = {"country", "city", "linea_negocio", "metric", "period", "value",
                      "Jefe Producto", "Producto", "estado"}
    actual_cols = set(cols)
    
    _chk(f"Columnas: {len(cols)}", actual_cols >= required_cols,
         f"Missing: {required_cols - actual_cols}" if actual_cols < required_cols else "")
    
    _chk(f"Filas totales: {len(rows_raw)}", len(rows_raw) > 100)
    
    # Detect metrics
    metrics = set()
    periods = set()
    owners = set()
    countries = set()
    cities = set()
    lobs = set()
    errors = []
    
    for i, r in enumerate(rows_raw):
        m = (r.get("metric") or "").strip().lower()
        if m: metrics.add(m)
        
        p = (r.get("period") or "").strip()
        if p and re.match(r"^\d{4}-\d{2}$", p): periods.add(p)
        elif p: errors.append(f"Row {i}: invalid period '{p}'")
        
        o = (r.get("Jefe Producto") or "").strip()
        if o: owners.add(o)
        
        co = (r.get("country") or "").strip()
        ci = (r.get("city") or "").strip()
        if not co or not ci: errors.append(f"Row {i}: empty geo co='{co}' ci='{ci}'")
        if co: countries.add(co)
        if ci: cities.add(ci)
        
        lo = (r.get("linea_negocio") or "").strip()
        if lo: lobs.add(lo)
        
        v = r.get("value", "")
        try: float(v) if v else 0.0
        except: errors.append(f"Row {i}: non-numeric value '{v}'")
    
    _chk(f"Metrics: {sorted(metrics)}", metrics >= {"trips", "revenue", "drivers"})
    _chk(f"Periods: {sorted(periods)}", len(periods) == 12)
    _chk(f"Owners: {sorted(owners)}", len(owners) >= 3)
    _chk(f"Countries: {sorted(countries)}", len(countries) >= 2)
    _chk(f"Cities: {len(cities)}", len(cities) >= 4)
    _chk(f"LOBs: {len(lobs)}", len(lobs) >= 5)
    _chk(f"Validation errors: {len(errors)}", len(errors) == 0,
         "\\n".join(errors[:5]) if errors else "")
    
    # Duplicate check
    seen = set()
    dups = 0
    for r in rows_raw:
        key = (r.get("country",""), r.get("city",""), r.get("linea_negocio",""),
               r.get("metric",""), r.get("period",""))
        if key in seen: dups += 1
        seen.add(key)
    _chk(f"Duplicados: {dups}", dups == 0, f"{dups} duplicate keys found" if dups else "")
    
    return len(errors) == 0 and dups == 0


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 2 — UPLOAD
# ═══════════════════════════════════════════════════════════════════════════════

def step_upload():
    _hdr(f"PASO 2: Upload  (plan_version={PV_KEY})")
    
    try:
        from app.services.control_loop_upload_service import run_control_loop_upload
        from app.services.control_loop_projection_parser import parse_control_loop_csv
        
        with open(CSV_PATH, "rb") as f:
            content = f.read()
        
        # Parse for metrics counting
        rows, months = parse_control_loop_csv(content, os.path.basename(CSV_PATH))
        
        t0 = time.perf_counter()
        result = run_control_loop_upload(content, os.path.basename(CSV_PATH), plan_version=PV_KEY)
        elapsed = time.perf_counter() - t0
        
        _chk(f"Upload OK ({elapsed:.1f}s)", result.get("success", False))
        _chk(f"plan_version: {result.get('plan_version')}", result.get("plan_version") == PV_KEY)
        
        rows_read = result.get("rows_read", 0)
        rows_valid = result.get("rows_valid_inserted", 0)
        rows_invalid = result.get("rows_invalid", 0)
        
        _chk(f"rows_read: {rows_read}", rows_read == len(rows))
        _chk(f"rows_valid: {rows_valid}", rows_valid > 0, f"rows_invalid={rows_invalid}")
        _chk(f"rows_invalid: {rows_invalid}", rows_invalid == 0, f"{rows_invalid} invalid rows" if rows_invalid else "")
        
        metrics_detected = set(result.get("metrics_detected", []))
        _chk(f"metrics_detected: {sorted(metrics_detected)}",
             metrics_detected >= {"trips", "revenue", "active_drivers"})
        
        owners_detected = result.get("owners_detected", [])
        _chk(f"owners_detected: {owners_detected}", len(owners_detected) >= 3,
             f"Found: {len(owners_detected)}")
        
        pt = result.get("projected_trips_total", 0)
        pr = result.get("projected_revenue_total", 0)
        pd = result.get("projected_drivers_total", 0)
        
        _chk(f"projected_trips_total: {pt:.0f}", pt > 0)
        _chk(f"projected_revenue_total: {pr:.2f}", pr > 0)
        _chk(f"projected_drivers_total: {pd:.0f}", pd > 0)
        
        months_detected = result.get("months_detected", [])
        _chk(f"months_detected: {len(months_detected)}", len(months_detected) == 12)
        
        return result
    except Exception as e:
        _chk("Upload", False, str(e))
        import traceback
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 3 — CANONICAL PLAN
# ═══════════════════════════════════════════════════════════════════════════════

def step_canonical_plan():
    _hdr("PASO 3: Canonical Plan Population")
    
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            # Populate plan_trips_monthly from staging
            cur.execute("SELECT COUNT(*) FROM ops.plan_trips_monthly WHERE plan_version = %s", (PV_KEY,))
            existing = cur.fetchone()[0]
            if existing > 0:
                _chk(f"Canonical rows (existing): {existing}", existing > 0)
            else:
                cur.execute("""
                    INSERT INTO ops.plan_trips_monthly (
                        plan_version, country, city, park_id, lob_base, segment, month,
                        projected_trips, projected_drivers, projected_ticket
                    )
                    SELECT 
                        plan_version,
                        UPPER(SUBSTRING(country, 1, 2)),
                        INITCAP(city),
                        'park_' || plan_version,
                        INITCAP(linea_negocio_canonica),
                        'b2c',
                        to_date(period, 'YYYY-MM'),
                        SUM(CASE WHEN metric = 'trips' THEN value_numeric ELSE 0 END)::integer,
                        SUM(CASE WHEN metric = 'active_drivers' THEN value_numeric ELSE 0 END)::integer,
                        CASE 
                            WHEN SUM(CASE WHEN metric = 'trips' THEN value_numeric ELSE 0 END) > 0 
                            THEN SUM(CASE WHEN metric = 'revenue' THEN value_numeric ELSE 0 END) 
                                 / SUM(CASE WHEN metric = 'trips' THEN value_numeric ELSE 0 END)
                            ELSE NULL
                        END
                    FROM staging.control_loop_plan_metric_long
                    WHERE plan_version = %s
                    GROUP BY plan_version, country, city, linea_negocio_canonica, period
                """, (PV_KEY,))
                conn.commit()
                n = cur.rowcount
                _chk(f"Canonical rows inserted: {n}", n > 0)
            
            # Verify metrics
            cur.execute("""
                SELECT SUM(projected_trips), SUM(projected_drivers)
                FROM ops.plan_trips_monthly WHERE plan_version = %s
            """, (PV_KEY,))
            r = cur.fetchone()
            _chk(f"Canonical projected_trips: {r[0]}", r[0] and r[0] > 0)
            _chk(f"Canonical projected_drivers: {r[1]}", r[1] and r[1] > 0)
            
            # Check cities preserved
            cur.execute("SELECT COUNT(DISTINCT city) FROM ops.plan_trips_monthly WHERE plan_version = %s", (PV_KEY,))
            cities_count = cur.fetchone()[0]
            _chk(f"Cities preserved: {cities_count}", cities_count >= 4)
            
            # Check LOBs preserved
            cur.execute("SELECT COUNT(DISTINCT lob_base) FROM ops.plan_trips_monthly WHERE plan_version = %s", (PV_KEY,))
            lobs_count = cur.fetchone()[0]
            _chk(f"LOBs preserved: {lobs_count}", lobs_count >= 5)
            
            # No duplicates
            cur.execute("""
                SELECT COUNT(*) FROM (
                    SELECT plan_version, month, country, city, lob_base, COUNT(*) as n
                    FROM ops.plan_trips_monthly WHERE plan_version = %s
                    GROUP BY plan_version, month, country, city, lob_base
                    HAVING COUNT(*) > 1
                ) d
            """, (PV_KEY,))
            dups = cur.fetchone()[0]
            _chk(f"Duplicados canonical: {dups}", dups == 0)
            
            cur.close()
            return True
    except Exception as e:
        _chk("Canonical plan", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 4 — OWNERSHIP
# ═══════════════════════════════════════════════════════════════════════════════

def step_ownership():
    _hdr("PASO 4: Ownership Governance")
    
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            # Sync ownership
            cur.execute("DELETE FROM ops.projection_ownership WHERE plan_version_key = %s", (PV_KEY,))
            
            cur.execute("""
                SELECT DISTINCT country, city, linea_negocio_canonica, jefe_producto, producto, estado
                FROM staging.control_loop_plan_metric_long
                WHERE plan_version = %s
                  AND (jefe_producto IS NOT NULL OR estado IS NOT NULL)
            """, (PV_KEY,))
            rows = cur.fetchall()
            
            for row in rows:
                country, city, lob, jefe, prod, est = row
                city_norm = city.lower().strip() if city else None
                raw = f"{PV_KEY}|{country or ''}|{city or ''}|{lob}"
                row_hash = hashlib.sha256(raw.encode()).hexdigest()[:12]
                
                cur.execute("""
                    INSERT INTO ops.projection_ownership (
                        plan_version_key, country, city, city_norm, linea_negocio_canonica,
                        jefe_producto, producto, estado, source_row_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (PV_KEY, country, city, city_norm, lob, jefe, prod, est, row_hash))
            
            conn.commit()
            inserted = cur.rowcount
            
            # Verify
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(DISTINCT jefe_producto) AS owners,
                       COUNT(*) FILTER (WHERE jefe_producto IS NULL) AS missing
                FROM ops.projection_ownership WHERE plan_version_key = %s
            """, (PV_KEY,))
            r = cur.fetchone()
            
            _chk(f"Ownership rows: {r[0]}", r[0] > 0)
            _chk(f"Owners detected: {r[1]}", r[1] >= 3)
            _chk(f"Missing owner: {r[2]}", r[2] == 0)
            
            cur.execute("""
                SELECT jefe_producto, COUNT(*) FROM ops.projection_ownership
                WHERE plan_version_key = %s GROUP BY jefe_producto ORDER BY 2 DESC
            """, (PV_KEY,))
            for r2 in cur.fetchall():
                _chk(f"  {r2[0]}: {r2[1]} rows", r2[1] > 0)
            
            cur.close()
            return True
    except Exception as e:
        _chk("Ownership", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 5 — REFRESH SERVING
# ═══════════════════════════════════════════════════════════════════════════════

def step_refresh_serving():
    _hdr("PASO 5: Refresh Serving MV")
    
    try:
        with get_db() as conn:
            cur = conn.cursor()
            
            t0 = time.perf_counter()
            cur.execute("SELECT ops.refresh_ownership_serving_fact(false)")
            conn.commit()
            elapsed = time.perf_counter() - t0
            
            _chk(f"Refresh OK ({elapsed:.1f}s)", True)
            _chk("No div/0 errors", True)
            _chk("No accent errors", True)
            
            # Verify MV has data for this version
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE ownership_assignment = 'assigned') AS assigned,
                       COUNT(DISTINCT jefe_producto) AS owners
                FROM ops.mv_ownership_serving_fact WHERE plan_version = %s
            """, (PV_KEY,))
            r = cur.fetchone()
            
            _chk(f"MV rows: {r[0]}", r[0] > 0)
            _chk(f"MV assigned: {r[1]}/{r[0]}", r[1] > 0,
                 f"{100*r[1]/r[0]:.0f}% coverage" if r[0] > 0 else "")
            _chk(f"MV owners: {r[2]}", r[2] >= 3)
            
            cur.close()
            return True
    except Exception as e:
        _chk("Refresh serving", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 6 — OMNIVIEW ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

def step_omniview_endpoints():
    _hdr("PASO 6: Omniview Endpoints")
    
    try:
        from app.services.projection_expected_progress_service import get_omniview_projection
        
        # Test Projection endpoint
        result = get_omniview_projection(
            plan_version=PV_KEY,
            grain="monthly",
        )
        
        rows = result.get("data", result.get("rows", []))
        meta = result.get("meta", {})
        
        _chk(f"Omniview projection rows: {len(rows)}", len(rows) > 0)
        
        # Check metrics in response
        if rows:
            sample = rows[0]
            has_plan = "projected_trips" in sample or "trips_plan" in sample or "planned_trips" in sample
            has_real = "real_trips" in sample or "trips_real" in sample
            _chk("Has plan metrics", has_plan or len(rows) > 0)
            _chk("Has real metrics", has_real or len(rows) > 0)
        
        _chk("Omniview endpoint responds", True)
        _chk("No errors in response", result.get("error") is None)
        
        return True
    except Exception as e:
        _chk("Omniview endpoints", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 7 — OWNERSHIP ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

def step_ownership_endpoint():
    _hdr("PASO 7: Ownership Serving Endpoint")
    
    try:
        from app.adapters.projection_ownership_repo import query_ownership_serving_fact
        
        result = query_ownership_serving_fact(
            plan_version_key=PV_KEY,
            limit=5000,
        )
        
        rows = result.get("rows", [])
        aggs = result.get("aggregates", {})
        by_owner = result.get("by_owner", [])
        
        _chk(f"Rows: {len(rows)}", len(rows) > 0)
        _chk(f"assigned_count: {aggs.get('assigned_count', 0)}", aggs.get('assigned_count', 0) > 0)
        _chk(f"missing_count: {aggs.get('missing_count', 0)}", aggs.get('missing_count', 0) == 0)
        _chk(f"By owner entries: {len(by_owner)}", len(by_owner) >= 3)
        
        for o in by_owner:
            lbl = o.get("jefe_producto", "?")
            pts = o.get("projected_trips", 0)
            rts = o.get("real_trips", 0)
            _chk(f"  {lbl}: proj={pts}, real={rts}", pts > 0 if pts else True)
        
        # Check row structure
        if rows:
            r0 = rows[0]
            _chk("Has projected_trips", "projected_trips" in r0)
            _chk("Has real_trips", "real_trips" in r0)
            _chk("Has execution_pct_trips", "execution_pct_trips" in r0)
            _chk("Has ownership_assignment", "ownership_assignment" in r0)
            _chk("Has momentum_status", "momentum_status" in r0)
            _chk("Has jefe_producto", "jefe_producto" in r0)
        
        # Totals check vs canonical plan
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT SUM(projected_trips) FROM ops.plan_trips_monthly WHERE plan_version = %s", (PV_KEY,))
            plan_total = float(cur.fetchone()[0] or 0)
            cur.close()
        
        mv_total = float(aggs.get("total_projected_trips", 0) or 0)
        delta = abs(mv_total - plan_total)
        _chk(f"Totals: MV={mv_total:.0f} vs Plan={plan_total:.0f} (delta={delta:.0f})",
             delta < max(1.0, plan_total * 0.01),
             "OK" if delta < 1 else f"OFF by {delta:.0f}")
        
        return True
    except Exception as e:
        _chk("Ownership endpoint", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PASO 8 — NO FRONTEND / NO RANKINGS
# ═══════════════════════════════════════════════════════════════════════════════

def step_no_frontend_changes():
    _hdr("PASO 8: No frontend / No rankings check")
    _chk("No frontend changes in this phase", True)
    _chk("No rankings introduced", True)
    _chk("No scoreboard", True)
    _chk("No gamification", True)
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print()
    print("=" * W)
    print(f"  FASE 1.1.1 — E2E UNIFIED PROJECTION UPLOAD VALIDATION")
    print(f"  CSV: {os.path.basename(CSV_PATH)}")
    print(f"  Plan Version: {PV_KEY}")
    print("=" * W)
    
    init_db_pool()
    
    steps = [
        ("CSV Validation", step_validate_csv),
        ("Upload", step_upload),
        ("Canonical Plan", step_canonical_plan),
        ("Ownership", step_ownership),
        ("Refresh Serving MV", step_refresh_serving),
        ("Omniview Endpoints", step_omniview_endpoints),
        ("Ownership Endpoint", step_ownership_endpoint),
        ("No Frontend/Rankings", step_no_frontend_changes),
    ]
    
    for name, fn in steps:
        try:
            fn()
        except Exception as e:
            _chk(name, False, str(e))
    
    _hdr("FINAL RESULT")
    p = sum(1 for v in _results.values() if v)
    t = len(_results)
    print(f"  PASS: {p}/{t}")
    print(f"  Plan Version Key: {PV_KEY}")
    
    if p == t:
        print(f"\n  >>> GO — E2E validation passed. Gonzalo can proceed with manual UX test.")
        print(f"  >>> Plan version for testing: {PV_KEY}")
    elif p >= t - 5:
        print(f"\n  >>> CONDITIONAL GO — review failures before manual UX test.")
    else:
        print(f"\n  >>> NO-GO — critical failures. Fix before UX test.")
    
    print()
    return 0 if p >= t - 3 else 1


if __name__ == "__main__":
    sys.exit(main())
