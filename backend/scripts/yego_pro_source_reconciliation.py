"""
Yego Pro Profitability P2.3 -- Source Reconciliation Script
READ-ONLY. No data modifications.

Inspects:
  - public.module_weekly_billing
  - public.module_driver_closes
  - public.module_calculated_shifts (or equivalent)
  - public.trips_2026

Park: 64085dd85e124e2c808806f70d527ea8 (Lima)

Outputs CSV reports to reports/
"""
import sys
import os
import csv
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import init_db_pool, get_db

PARK_ID = "64085dd85e124e2c808806f70d527ea8"
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")

os.makedirs(REPORTS_DIR, exist_ok=True)

def write_csv(filename, rows, fieldnames=None):
    path = os.path.join(REPORTS_DIR, filename)
    if not rows:
        print(f"  [SKIP] {filename} -- no rows")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if isinstance(rows[0], dict) else None
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [OK] {filename} -- {len(rows)} rows")

def safe(v):
    if v is None:
        return None
    return v

def run():
    print("=" * 70)
    print("YEGO PRO PROFITABILITY P2.3 -- SOURCE RECONCILIATION")
    print(f"Park: {PARK_ID}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    init_db_pool()

    source_inventory = []
    table_grains = []
    reconciliation_summary = []
    metric_sot = []
    data_gaps = []
    findings = []

    with get_db() as conn:
        cur = conn.cursor()

        # ============================================================
        # PHASE 1 -- SCHEMA DISCOVERY
        # ============================================================
        print("\n--- PHASE 1: SCHEMA DISCOVERY ---")

        tables_to_check = [
            ("public", "module_weekly_billing"),
            ("public", "module_driver_closes"),
            ("public", "module_calculated_shifts"),
        ]

        discovered_tables = {}

        for schema, table in tables_to_check:
            full_name = f"{schema}.{table}"
            print(f"\n  Checking {full_name}...")

            cur.execute(
                "SELECT to_regclass(%s) IS NOT NULL AS exists_flag",
                (full_name,),
            )
            row = cur.fetchone()
            exists = bool(row and row[0])

            if not exists:
                print(f"    TABLE DOES NOT EXIST: {full_name}")
                source_inventory.append({
                    "schema": schema, "table": table, "exists": False,
                    "column_count": 0, "row_count": 0,
                    "min_date": None, "max_date": None,
                    "has_driver_id": False, "has_vehicle_id": False,
                    "has_park_id": False, "notes": "TABLE NOT FOUND IN DATABASE",
                })
                continue

            discovered_tables[table] = True

            cur.execute("""
                SELECT column_name, data_type, is_nullable, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, table))
            columns = cur.fetchall()

            print(f"    Columns ({len(columns)}):")
            col_names = []
            for col in columns:
                col_name, dtype, nullable, max_len = col
                col_names.append(col_name)
                length_info = f"({max_len})" if max_len else ""
                print(f"      {col_name}: {dtype}{length_info} {'NULL' if nullable == 'YES' else 'NOT NULL'}")

            cur.execute(f"SELECT COUNT(*) FROM {full_name}")
            total_rows = cur.fetchone()[0]
            print(f"    Total rows: {total_rows}")

            has_driver = "driver_id" in col_names
            has_vehicle = any(c in col_names for c in ["vehicle_id", "car_id", "placa"])
            has_park = "park_id" in col_names

            date_cols = [c for c in col_names if c in ("fecha", "date", "fecha_inicio", "fecha_fin", "created_at", "fecha_inicio_viaje")]
            min_date = max_date = None
            for dc in date_cols:
                cur.execute(f"SELECT MIN({dc})::text, MAX({dc})::text FROM {full_name}")
                mn, mx = cur.fetchone()
                if mn:
                    if min_date is None or mn < min_date:
                        min_date = mn
                    if max_date is None or mx > max_date:
                        max_date = mx
                print(f"    {dc}: {mn} -> {mx}")

            money_cols = [c for c in col_names if any(k in c for k in [
                "monto", "pago", "costo", "gasto", "ingreso", "utilidad", "comision",
                "bono", "liquida", "total", "gnv", "gasolina", "resta", "precio",
            ])]

            null_report = {}
            for mc in money_cols + ["driver_id"] + ([c for c in col_names if c in ("vehicle_id", "car_id", "placa")]):
                if mc in col_names:
                    cur.execute(f"SELECT COUNT(*) FROM {full_name} WHERE {mc} IS NULL")
                    nulls = cur.fetchone()[0]
                    if nulls > 0:
                        null_report[mc] = nulls
            if null_report:
                print(f"    Nulls in key cols: {null_report}")

            park_filtered_rows = total_rows
            if has_driver:
                cur.execute(f"""
                    SELECT COUNT(*) FROM {full_name}
                    WHERE driver_id IN (
                        SELECT driver_id FROM public.drivers WHERE park_id = %s
                    )
                """, (PARK_ID,))
                park_filtered_rows = cur.fetchone()[0]
                print(f"    Rows for park {PARK_ID}: {park_filtered_rows}")

            source_inventory.append({
                "schema": schema, "table": table, "exists": True,
                "column_count": len(columns), "row_count": total_rows,
                "park_filtered_rows": park_filtered_rows,
                "min_date": min_date, "max_date": max_date,
                "has_driver_id": has_driver, "has_vehicle_id": has_vehicle,
                "has_park_id": has_park,
                "money_columns": "; ".join(money_cols),
                "critical_nulls": json.dumps(null_report) if null_report else "",
                "notes": "",
            })

        print("\n  Checking for similar shift tables...")
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name LIKE '%shift%' OR table_name LIKE '%turno%' OR table_name LIKE '%calculated%'
            ORDER BY table_schema, table_name
        """)
        shift_tables = cur.fetchall()
        if shift_tables:
            print(f"    Found shift-related tables: {shift_tables}")
        else:
            print("    No shift-related tables found. Shifts are DERIVED from trips_2026 timestamps.")

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'trips_2026'
            ORDER BY ordinal_position
        """)
        trips_cols = cur.fetchall()
        print(f"\n  trips_2026 columns ({len(trips_cols)}):")
        trips_col_names = []
        for col in trips_cols:
            trips_col_names.append(col[0])
            print(f"    {col[0]}: {col[1]}")

        cur.execute("""
            SELECT COUNT(*),
                   MIN(fecha_inicio_viaje::date)::text,
                   MAX(fecha_inicio_viaje::date)::text,
                   COUNT(DISTINCT conductor_id)
            FROM public.trips_2026
            WHERE park_id = %s AND condicion = 'Completado'
        """, (PARK_ID,))
        tr = cur.fetchone()
        print(f"    Park trips: {tr[0]} rows, {tr[1]} -> {tr[2]}, {tr[3]} drivers")

        source_inventory.append({
            "schema": "public", "table": "trips_2026", "exists": True,
            "column_count": len(trips_cols), "row_count": tr[0],
            "park_filtered_rows": tr[0],
            "min_date": tr[1], "max_date": tr[2],
            "has_driver_id": True, "has_vehicle_id": "car_number" in trips_col_names,
            "has_park_id": True,
            "money_columns": "precio_yango_pro",
            "critical_nulls": "",
            "notes": f"{tr[3]} distinct drivers for park",
        })

        write_csv("yego_pro_source_inventory.csv", source_inventory)

        # ============================================================
        # PHASE 2 -- GRAIN ANALYSIS
        # ============================================================
        print("\n--- PHASE 2: GRAIN ANALYSIS ---")

        if "module_weekly_billing" in discovered_tables:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(DISTINCT driver_id) AS distinct_drivers,
                    COUNT(DISTINCT fecha_inicio) AS distinct_weeks,
                    COUNT(DISTINCT (driver_id, fecha_inicio)) AS distinct_driver_weeks
                FROM public.module_weekly_billing
                WHERE driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
            """, (PARK_ID,))
            g = cur.fetchone()
            grain_billing = "driver + week" if g[0] == g[3] else "driver + week (with possible duplicates)"
            print(f"  module_weekly_billing: {g[0]} rows, {g[1]} drivers, {g[2]} weeks, {g[3]} driver-weeks -> grain: {grain_billing}")
            table_grains.append({
                "table": "module_weekly_billing",
                "total_rows": g[0], "distinct_drivers": g[1],
                "distinct_periods": g[2], "distinct_grain_combos": g[3],
                "grain": grain_billing,
                "grain_keys": "driver_id + fecha_inicio",
                "period_type": "weekly (fecha_inicio, fecha_fin)",
                "has_shift": False,
            })

        if "module_driver_closes" in discovered_tables:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(DISTINCT driver_id) AS distinct_drivers,
                    COUNT(DISTINCT fecha) AS distinct_dates,
                    COUNT(DISTINCT (driver_id, fecha)) AS distinct_driver_dates
                FROM public.module_driver_closes
                WHERE driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
            """, (PARK_ID,))
            g = cur.fetchone()
            grain_closes = "driver + date" if g[0] == g[3] else "driver + date (with possible duplicates)"
            print(f"  module_driver_closes: {g[0]} rows, {g[1]} drivers, {g[2]} dates, {g[3]} driver-dates -> grain: {grain_closes}")
            table_grains.append({
                "table": "module_driver_closes",
                "total_rows": g[0], "distinct_drivers": g[1],
                "distinct_periods": g[2], "distinct_grain_combos": g[3],
                "grain": grain_closes,
                "grain_keys": "driver_id + fecha",
                "period_type": "daily (fecha)",
                "has_shift": "calculated_shift_ids references shifts",
            })

            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE calculated_shift_ids IS NOT NULL) AS has_shifts,
                       COUNT(*) FILTER (WHERE calculated_shift_ids IS NULL) AS no_shifts,
                       COUNT(*) AS total
                FROM public.module_driver_closes
                WHERE driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
            """, (PARK_ID,))
            sr = cur.fetchone()
            print(f"    calculated_shift_ids: {sr[0]} with values, {sr[1]} null, {sr[2]} total")

        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(DISTINCT conductor_id) AS distinct_drivers,
                COUNT(DISTINCT fecha_inicio_viaje::date) AS distinct_dates,
                COUNT(DISTINCT (conductor_id, fecha_inicio_viaje::date)) AS distinct_driver_dates
            FROM public.trips_2026
            WHERE park_id = %s AND condicion = 'Completado'
        """, (PARK_ID,))
        g = cur.fetchone()
        print(f"  trips_2026: {g[0]} rows, {g[1]} drivers, {g[2]} dates, {g[3]} driver-dates -> grain: trip (individual)")
        table_grains.append({
            "table": "trips_2026",
            "total_rows": g[0], "distinct_drivers": g[1],
            "distinct_periods": g[2], "distinct_grain_combos": g[3],
            "grain": "individual trip",
            "grain_keys": "trip row (no explicit PK visible)",
            "period_type": "timestamp (fecha_inicio_viaje)",
            "has_shift": "DERIVED from EXTRACT(HOUR FROM fecha_inicio_viaje)",
        })

        write_csv("yego_pro_table_grains.csv", table_grains)

        # ============================================================
        # PHASE 3 -- CROSS-TABLE RECONCILIATION
        # ============================================================
        print("\n--- PHASE 3: CROSS-TABLE RECONCILIATION ---")

        # A. trips_2026 vs module_weekly_billing (production vs billing)
        print("\n  A. trips_2026 vs module_weekly_billing")
        cur.execute("""
            WITH park_drivers AS (
                SELECT driver_id FROM public.drivers WHERE park_id = %s
            ),
            weekly_trips AS (
                SELECT
                    DATE_TRUNC('week', fecha_inicio_viaje)::date AS week_start,
                    COUNT(*) AS trip_count,
                    COUNT(DISTINCT conductor_id) AS drivers,
                    SUM(precio_yango_pro) AS revenue
                FROM public.trips_2026
                WHERE park_id = %s AND condicion = 'Completado'
                GROUP BY DATE_TRUNC('week', fecha_inicio_viaje)::date
            ),
            weekly_billing AS (
                SELECT
                    fecha_inicio AS week_start,
                    SUM(total_viajes) AS billing_trips,
                    COUNT(DISTINCT driver_id) AS billing_drivers,
                    SUM(monto_total_producido) AS billing_revenue
                FROM public.module_weekly_billing
                WHERE driver_id IN (SELECT driver_id FROM park_drivers)
                GROUP BY fecha_inicio
            )
            SELECT
                COALESCE(t.week_start, b.week_start) AS week,
                t.trip_count AS trips_production,
                b.billing_trips AS trips_billing,
                CASE WHEN t.trip_count > 0 AND b.billing_trips > 0
                     THEN t.trip_count - b.billing_trips ELSE NULL END AS trips_diff,
                t.revenue AS revenue_production,
                b.billing_revenue AS revenue_billing,
                CASE WHEN t.revenue > 0 AND b.billing_revenue > 0
                     THEN ROUND((t.revenue - b.billing_revenue)::numeric, 2) ELSE NULL END AS revenue_diff,
                t.drivers AS drivers_production,
                b.billing_drivers AS drivers_billing
            FROM weekly_trips t
            FULL OUTER JOIN weekly_billing b ON t.week_start = b.week_start
            ORDER BY week DESC
        """, (PARK_ID, PARK_ID))
        recon_a_cols = [d[0] for d in cur.description]
        recon_a_rows = [dict(zip(recon_a_cols, r)) for r in cur.fetchall()]

        for r in recon_a_rows:
            reconciliation_summary.append({
                "comparison": "trips_2026 vs module_weekly_billing",
                "period": str(r["week"]),
                "metric": "trips",
                "value_source_a": r["trips_production"],
                "value_source_b": r["trips_billing"],
                "difference": r["trips_diff"],
                "status": "MATCH" if r["trips_diff"] is not None and abs(r["trips_diff"]) <= 2 else (
                    "MISMATCH" if r["trips_diff"] is not None else "MISSING_SIDE"),
            })
            reconciliation_summary.append({
                "comparison": "trips_2026 vs module_weekly_billing",
                "period": str(r["week"]),
                "metric": "revenue",
                "value_source_a": r["revenue_production"],
                "value_source_b": r["revenue_billing"],
                "difference": r["revenue_diff"],
                "status": "MATCH" if r["revenue_diff"] is not None and abs(float(r["revenue_diff"])) < 50 else (
                    "MISMATCH" if r["revenue_diff"] is not None else "MISSING_SIDE"),
            })

        print(f"    {len(recon_a_rows)} weeks compared")
        mismatches_a = [r for r in recon_a_rows if r["trips_diff"] is not None and abs(r["trips_diff"]) > 2]
        print(f"    Trip mismatches (>2): {len(mismatches_a)}")

        # B. module_driver_closes vs module_weekly_billing (daily close vs weekly billing)
        if "module_driver_closes" in discovered_tables:
            print("\n  B. module_driver_closes vs module_weekly_billing")
            cur.execute("""
                WITH park_drivers AS (
                    SELECT driver_id FROM public.drivers WHERE park_id = %s
                ),
                weekly_closes AS (
                    SELECT
                        driver_id,
                        DATE_TRUNC('week', fecha)::date AS week_start,
                        SUM(total_ingresos) AS close_income,
                        SUM(total_gastos) AS close_expenses,
                        SUM(resta) AS close_remainder,
                        COUNT(*) AS close_days
                    FROM public.module_driver_closes
                    WHERE driver_id IN (SELECT driver_id FROM park_drivers)
                    GROUP BY driver_id, DATE_TRUNC('week', fecha)::date
                ),
                billing AS (
                    SELECT
                        driver_id,
                        fecha_inicio AS week_start,
                        monto_total_producido AS billing_revenue,
                        pago_total AS billing_payout,
                        utilidad AS billing_profit,
                        gasto_combustible AS billing_fuel,
                        gasto_mantenimiento AS billing_maintenance
                    FROM public.module_weekly_billing
                    WHERE driver_id IN (SELECT driver_id FROM park_drivers)
                )
                SELECT
                    COALESCE(c.week_start, b.week_start) AS week,
                    COALESCE(c.driver_id, b.driver_id) AS driver_id,
                    c.close_income,
                    c.close_expenses,
                    c.close_remainder,
                    c.close_days,
                    b.billing_revenue,
                    b.billing_payout,
                    b.billing_profit,
                    b.billing_fuel,
                    CASE WHEN c.close_income IS NOT NULL AND b.billing_revenue IS NOT NULL
                         THEN ROUND((c.close_income - b.billing_revenue)::numeric, 2)
                         ELSE NULL END AS income_vs_revenue_diff,
                    CASE WHEN c.driver_id IS NULL THEN 'BILLING_ONLY'
                         WHEN b.driver_id IS NULL THEN 'CLOSE_ONLY'
                         ELSE 'BOTH' END AS join_status
                FROM weekly_closes c
                FULL OUTER JOIN billing b ON c.driver_id = b.driver_id AND c.week_start = b.week_start
                ORDER BY week DESC, driver_id
                LIMIT 200
            """, (PARK_ID,))
            recon_b_cols = [d[0] for d in cur.description]
            recon_b_rows = [dict(zip(recon_b_cols, r)) for r in cur.fetchall()]

            both_count = sum(1 for r in recon_b_rows if r["join_status"] == "BOTH")
            billing_only = sum(1 for r in recon_b_rows if r["join_status"] == "BILLING_ONLY")
            close_only = sum(1 for r in recon_b_rows if r["join_status"] == "CLOSE_ONLY")
            print(f"    {len(recon_b_rows)} driver-weeks: {both_count} BOTH, {billing_only} BILLING_ONLY, {close_only} CLOSE_ONLY")

            for r in recon_b_rows:
                reconciliation_summary.append({
                    "comparison": "module_driver_closes vs module_weekly_billing",
                    "period": f"{r['week']} | {r['driver_id']}",
                    "metric": "income_vs_revenue",
                    "value_source_a": r["close_income"],
                    "value_source_b": r["billing_revenue"],
                    "difference": r["income_vs_revenue_diff"],
                    "status": r["join_status"] if r["join_status"] != "BOTH" else (
                        "MATCH" if r["income_vs_revenue_diff"] is not None and abs(float(r["income_vs_revenue_diff"])) < 50 else "MISMATCH"),
                })

            if close_only > 0:
                data_gaps.append({
                    "gap_type": "CLOSE_WITHOUT_BILLING",
                    "table": "module_driver_closes",
                    "count": close_only,
                    "description": f"{close_only} driver-week records in closes without matching billing",
                    "severity": "MEDIUM",
                    "impact": "Daily settlement data exists but no weekly billing -- payout reconciliation incomplete",
                })
            if billing_only > 0:
                data_gaps.append({
                    "gap_type": "BILLING_WITHOUT_CLOSE",
                    "table": "module_weekly_billing",
                    "count": billing_only,
                    "description": f"{billing_only} driver-week records in billing without matching daily closes",
                    "severity": "LOW",
                    "impact": "Billing exists without daily settlement detail -- normal if close process is partial",
                })

        # C. trips_2026 vs module_driver_closes (production vs daily close)
        if "module_driver_closes" in discovered_tables:
            print("\n  C. trips_2026 vs module_driver_closes")
            cur.execute("""
                WITH park_drivers AS (
                    SELECT driver_id FROM public.drivers WHERE park_id = %s
                ),
                daily_trips AS (
                    SELECT
                        conductor_id AS driver_id,
                        fecha_inicio_viaje::date AS date,
                        COUNT(*) AS trips,
                        SUM(precio_yango_pro) AS revenue
                    FROM public.trips_2026
                    WHERE park_id = %s AND condicion = 'Completado'
                    GROUP BY conductor_id, fecha_inicio_viaje::date
                ),
                daily_closes AS (
                    SELECT
                        driver_id,
                        fecha AS date,
                        total_ingresos,
                        total_gastos,
                        resta
                    FROM public.module_driver_closes
                    WHERE driver_id IN (SELECT driver_id FROM park_drivers)
                )
                SELECT
                    COALESCE(t.date, c.date) AS date,
                    COUNT(DISTINCT t.driver_id) AS drivers_with_trips,
                    COUNT(DISTINCT c.driver_id) AS drivers_with_close,
                    SUM(t.trips) AS total_trips,
                    SUM(t.revenue) AS total_revenue,
                    SUM(c.total_ingresos) AS total_close_income,
                    COUNT(*) FILTER (WHERE t.driver_id IS NOT NULL AND c.driver_id IS NULL) AS trips_without_close,
                    COUNT(*) FILTER (WHERE t.driver_id IS NULL AND c.driver_id IS NOT NULL) AS close_without_trips
                FROM daily_trips t
                FULL OUTER JOIN daily_closes c ON t.driver_id = c.driver_id AND t.date = c.date
                GROUP BY COALESCE(t.date, c.date)
                ORDER BY date DESC
                LIMIT 60
            """, (PARK_ID, PARK_ID))
            recon_c_cols = [d[0] for d in cur.description]
            recon_c_rows = [dict(zip(recon_c_cols, r)) for r in cur.fetchall()]

            trips_no_close = sum(r["trips_without_close"] or 0 for r in recon_c_rows)
            close_no_trips = sum(r["close_without_trips"] or 0 for r in recon_c_rows)
            print(f"    {len(recon_c_rows)} days compared")
            print(f"    Driver-days with trips but no close: {trips_no_close}")
            print(f"    Driver-days with close but no trips: {close_no_trips}")

            if trips_no_close > 0:
                data_gaps.append({
                    "gap_type": "PRODUCTION_WITHOUT_CLOSE",
                    "table": "trips_2026 vs module_driver_closes",
                    "count": trips_no_close,
                    "description": f"{trips_no_close} driver-day records with production but no daily close",
                    "severity": "HIGH",
                    "impact": "Drivers with trips but no settlement -- payout not tracked for these days",
                })
            if close_no_trips > 0:
                data_gaps.append({
                    "gap_type": "CLOSE_WITHOUT_PRODUCTION",
                    "table": "module_driver_closes vs trips_2026",
                    "count": close_no_trips,
                    "description": f"{close_no_trips} driver-day records with daily close but no trips",
                    "severity": "MEDIUM",
                    "impact": "Settlement exists for days without trip production -- may be adjustments or errors",
                })

        write_csv("yego_pro_reconciliation_summary.csv", reconciliation_summary)

        # ============================================================
        # PHASE 4 -- METRIC SOURCE OF TRUTH
        # ============================================================
        print("\n--- PHASE 4: METRIC SOURCE OF TRUTH ---")

        sot_entries = [
            {"category": "Production", "metric": "trips", "source_of_truth": "trips_2026", "secondary_check": "module_weekly_billing.total_viajes", "fallback": "N/A", "confidence": "HIGH", "notes": "Trip-level granularity is the atomic source"},
            {"category": "Production", "metric": "revenue_gross", "source_of_truth": "trips_2026 (precio_yango_pro)", "secondary_check": "module_weekly_billing.monto_total_producido", "fallback": "N/A", "confidence": "HIGH", "notes": "Trip-level pricing from Yango Pro platform"},
            {"category": "Production", "metric": "km", "source_of_truth": "trips_2026 (distancia_km)", "secondary_check": "module_weekly_billing.km_recorrido", "fallback": "N/A", "confidence": "HIGH", "notes": "Trip distance (passenger km). billing km includes dead km"},
            {"category": "Production", "metric": "shift (day/night)", "source_of_truth": "DERIVED from trips_2026.fecha_inicio_viaje", "secondary_check": "N/A", "fallback": "N/A", "confidence": "HIGH", "notes": "06:00-17:59=DAY, 18:00-05:59=NIGHT. No native shift table."},
            {"category": "Production", "metric": "vehicle_active", "source_of_truth": "NOT_AVAILABLE", "secondary_check": "module_driver_closes.placa", "fallback": "N/A", "confidence": "LOW", "notes": "No vehicle-to-driver assignment table. placa in closes is partial."},
            {"category": "Production", "metric": "driver_active", "source_of_truth": "trips_2026 (DISTINCT conductor_id)", "secondary_check": "module_weekly_billing (DISTINCT driver_id)", "fallback": "N/A", "confidence": "HIGH", "notes": ""},
            {"category": "Settlement", "metric": "payout_driver", "source_of_truth": "module_weekly_billing.pago_total", "secondary_check": "module_driver_closes (daily)", "fallback": "N/A", "confidence": "HIGH", "notes": "Weekly billing is the official payout. Daily close is operational settlement."},
            {"category": "Settlement", "metric": "discounts", "source_of_truth": "module_weekly_billing.comision_app", "secondary_check": "N/A", "fallback": "N/A", "confidence": "HIGH", "notes": "Platform commission deducted from gross revenue"},
            {"category": "Settlement", "metric": "bonos", "source_of_truth": "module_weekly_billing.bono_yango + bono_adic_viajes", "secondary_check": "N/A", "fallback": "N/A", "confidence": "HIGH", "notes": "Yango bonus + additional trip bonus"},
            {"category": "Settlement", "metric": "advance_payments", "source_of_truth": "NOT_AVAILABLE", "secondary_check": "module_driver_closes.liquida_efectivo + liquida_yape", "fallback": "N/A", "confidence": "LOW", "notes": "Daily cash/yape settlements are in closes. No weekly aggregation."},
            {"category": "Settlement", "metric": "final_amount_payable", "source_of_truth": "module_weekly_billing.pago_total", "secondary_check": "module_driver_closes.resta (daily net)", "fallback": "N/A", "confidence": "HIGH", "notes": "pago_total = official weekly amount. resta = daily operational net."},
            {"category": "Billing", "metric": "real_income", "source_of_truth": "module_weekly_billing.monto_total_producido", "secondary_check": "trips_2026 revenue agg", "fallback": "N/A", "confidence": "HIGH", "notes": ""},
            {"category": "Billing", "metric": "real_expenses", "source_of_truth": "module_weekly_billing (fuel + maintenance + pago_total)", "secondary_check": "module_driver_closes (gasoline + gnv + otros)", "fallback": "N/A", "confidence": "HIGH", "notes": "Billing has structured cost breakdown"},
            {"category": "Billing", "metric": "fuel", "source_of_truth": "module_weekly_billing.gasto_combustible", "secondary_check": "module_driver_closes (gnv_soles + gasolina_soles)", "fallback": "N/A", "confidence": "HIGH", "notes": "Weekly is more reliable (structured). Daily has dual fuel types (GNV + gasoline)."},
            {"category": "Billing", "metric": "maintenance", "source_of_truth": "module_weekly_billing.gasto_mantenimiento", "secondary_check": "N/A", "fallback": "N/A", "confidence": "HIGH", "notes": "Only in weekly billing"},
            {"category": "Billing", "metric": "profit_loss", "source_of_truth": "module_weekly_billing.utilidad", "secondary_check": "DERIVED (revenue - all costs)", "fallback": "N/A", "confidence": "HIGH", "notes": "utilidad is the official P&L per driver per week"},
            {"category": "Billing", "metric": "weekly_close", "source_of_truth": "module_weekly_billing", "secondary_check": "N/A", "fallback": "N/A", "confidence": "HIGH", "notes": "Each row is a closed week for a driver"},
        ]
        metric_sot = sot_entries
        write_csv("yego_pro_metric_source_of_truth.csv", metric_sot)

        for e in sot_entries:
            print(f"  {e['category']}/{e['metric']}: SOT={e['source_of_truth']} [{e['confidence']}]")

        # ============================================================
        # PHASE 5 -- OPERATIONAL FINDINGS
        # ============================================================
        print("\n--- PHASE 5: OPERATIONAL FINDINGS ---")

        if "module_weekly_billing" in discovered_tables:
            cur.execute("""
                WITH park_drivers AS (
                    SELECT driver_id FROM public.drivers WHERE park_id = %s
                )
                SELECT
                    driver_id,
                    fecha_inicio AS week_start,
                    monto_total_producido AS revenue,
                    pago_total AS payout,
                    utilidad AS profit,
                    CASE WHEN monto_total_producido > 0
                         THEN ROUND((pago_total / monto_total_producido * 100)::numeric, 1)
                         ELSE NULL END AS payout_pct,
                    porcentaje_pago AS contractual_pct
                FROM public.module_weekly_billing
                WHERE driver_id IN (SELECT driver_id FROM park_drivers)
                  AND utilidad < 0
                ORDER BY utilidad ASC
                LIMIT 30
            """, (PARK_ID,))
            loss_cols = [d[0] for d in cur.description]
            loss_rows = [dict(zip(loss_cols, r)) for r in cur.fetchall()]
            if loss_rows:
                findings.append(f"FINDING: {len(loss_rows)} driver-weeks with LOSS (utilidad < 0). Worst: driver={loss_rows[0]['driver_id']}, profit={loss_rows[0]['profit']}, payout_pct={loss_rows[0]['payout_pct']}%")
                print(f"  {findings[-1]}")

            cur.execute("""
                WITH park_drivers AS (
                    SELECT driver_id FROM public.drivers WHERE park_id = %s
                )
                SELECT
                    driver_id,
                    fecha_inicio AS week_start,
                    pago_total AS payout,
                    monto_total_producido AS revenue,
                    ROUND((pago_total / NULLIF(monto_total_producido, 0) * 100)::numeric, 1) AS payout_pct
                FROM public.module_weekly_billing
                WHERE driver_id IN (SELECT driver_id FROM park_drivers)
                  AND pago_total > monto_total_producido
                ORDER BY (pago_total - monto_total_producido) DESC
                LIMIT 10
            """, (PARK_ID,))
            payout_exceed = cur.fetchall()
            if payout_exceed:
                findings.append(f"FINDING: {len(payout_exceed)} driver-weeks where PAYOUT > REVENUE (payout exceeds production)")
                print(f"  {findings[-1]}")
                data_gaps.append({
                    "gap_type": "PAYOUT_EXCEEDS_REVENUE",
                    "table": "module_weekly_billing",
                    "count": len(payout_exceed),
                    "description": "Driver-weeks where pago_total > monto_total_producido",
                    "severity": "HIGH",
                    "impact": "Guaranteed loss weeks -- payout to driver exceeds what they produced",
                })

            cur.execute("""
                WITH park_drivers AS (
                    SELECT driver_id FROM public.drivers WHERE park_id = %s
                ),
                billing_summary AS (
                    SELECT
                        fecha_inicio AS week_start,
                        SUM(monto_total_producido) AS revenue,
                        SUM(gasto_combustible) AS fuel,
                        SUM(gasto_mantenimiento) AS maint,
                        SUM(pago_total) AS payout,
                        SUM(utilidad) AS profit
                    FROM public.module_weekly_billing
                    WHERE driver_id IN (SELECT driver_id FROM park_drivers)
                    GROUP BY fecha_inicio
                    ORDER BY fecha_inicio DESC
                    LIMIT 12
                )
                SELECT *,
                    CASE WHEN revenue > 0 THEN ROUND((fuel/revenue*100)::numeric,1) ELSE NULL END AS fuel_pct,
                    CASE WHEN revenue > 0 THEN ROUND((maint/revenue*100)::numeric,1) ELSE NULL END AS maint_pct,
                    CASE WHEN revenue > 0 THEN ROUND((payout/revenue*100)::numeric,1) ELSE NULL END AS payout_pct
                FROM billing_summary
            """, (PARK_ID,))
            cost_cols = [d[0] for d in cur.description]
            cost_rows = [dict(zip(cost_cols, r)) for r in cur.fetchall()]
            if cost_rows:
                latest = cost_rows[0]
                findings.append(f"FINDING: Latest week cost breakdown -- fuel: {latest.get('fuel_pct')}%, maintenance: {latest.get('maint_pct')}%, payout: {latest.get('payout_pct')}% of revenue")
                print(f"  {findings[-1]}")

        if "module_driver_closes" in discovered_tables:
            cur.execute("""
                WITH park_drivers AS (
                    SELECT driver_id FROM public.drivers WHERE park_id = %s
                )
                SELECT COUNT(DISTINCT c.driver_id) AS close_drivers,
                       (SELECT COUNT(DISTINCT conductor_id) FROM public.trips_2026
                        WHERE park_id = %s AND condicion = 'Completado') AS trip_drivers
                FROM public.module_driver_closes c
                WHERE c.driver_id IN (SELECT driver_id FROM park_drivers)
            """, (PARK_ID, PARK_ID))
            dc = cur.fetchone()
            if dc:
                findings.append(f"FINDING: {dc[0]} drivers with closes vs {dc[1]} drivers with trips. Coverage: {round(dc[0]/max(dc[1],1)*100,1)}%")
                print(f"  {findings[-1]}")

            cur.execute("""
                WITH park_drivers AS (
                    SELECT driver_id FROM public.drivers WHERE park_id = %s
                )
                SELECT
                    COUNT(*) AS total_closes,
                    COUNT(*) FILTER (WHERE total_gastos > total_ingresos) AS expenses_exceed_income,
                    AVG(total_ingresos)::numeric(10,2) AS avg_daily_income,
                    AVG(total_gastos)::numeric(10,2) AS avg_daily_expenses,
                    AVG(resta)::numeric(10,2) AS avg_daily_remainder
                FROM public.module_driver_closes
                WHERE driver_id IN (SELECT driver_id FROM park_drivers)
            """, (PARK_ID,))
            close_stats = cur.fetchone()
            if close_stats:
                findings.append(f"FINDING: Daily closes -- {close_stats[1]}/{close_stats[0]} days where expenses > income. Avg income: {close_stats[2]}, expenses: {close_stats[3]}, remainder: {close_stats[4]}")
                print(f"  {findings[-1]}")

        if "module_calculated_shifts" not in discovered_tables:
            findings.append("FINDING: module_calculated_shifts DOES NOT EXIST. Shifts are DERIVED from trip timestamps. The column calculated_shift_ids in module_driver_closes is a text reference, not a FK to a separate table.")
            print(f"  {findings[-1]}")
            data_gaps.append({
                "gap_type": "TABLE_NOT_FOUND",
                "table": "module_calculated_shifts",
                "count": 0,
                "description": "Table does not exist in database. Shifts derived from trips_2026 timestamps.",
                "severity": "INFO",
                "impact": "No impact -- shift data is available via derivation. module_driver_closes.calculated_shift_ids is a text field.",
            })

        write_csv("yego_pro_data_gaps.csv", data_gaps)

        # ============================================================
        # PHASE 6 -- OUTPUTS ALREADY WRITTEN ABOVE
        # ============================================================
        print("\n--- PHASE 6: OUTPUT FILES ---")
        print(f"  All CSVs written to {REPORTS_DIR}")

        # ============================================================
        # PHASE 7 -- VERDICT
        # ============================================================
        print("\n" + "=" * 70)
        print("PHASE 7: VERDICT")
        print("=" * 70)

        verdicts = {
            "Q1_production_daily": {
                "answer": "trips_2026",
                "reason": "Atomic trip-level data with timestamp, driver, vehicle (car_number), price, distance, status. Highest granularity.",
            },
            "Q2_driver_payments": {
                "answer": "module_weekly_billing.pago_total",
                "reason": "Official weekly payout. module_driver_closes has daily operational settlement (liquida_efectivo + liquida_yape) but is not used in backend and has lower coverage.",
            },
            "Q3_weekly_profitability": {
                "answer": "module_weekly_billing.utilidad",
                "reason": "Contains full P&L: revenue, commission, fuel, maintenance, payout, profit per driver per week. Already used in serving MVs.",
            },
            "Q4_reliable_crosses": {
                "answer": "trips_2026 <-> module_weekly_billing (weekly aggregated trips and revenue)",
                "reason": "Both sources independently track trips and revenue. Cross-validation possible at week level.",
            },
            "Q5_unreliable_crosses": {
                "answer": "module_driver_closes <-> module_weekly_billing",
                "reason": "Different grains (daily vs weekly), different semantics (operational settlement vs billing), incomplete coverage. Not all driver-weeks have matching closes.",
            },
            "Q6_revelatory_info": {
                "answer": "module_driver_closes contains daily fuel costs (GNV + gasoline separately), odometer readings (km validation), and cash/yape settlement splits",
                "reason": "This data is NOT used anywhere in the current system. It could validate km_recorrido against odometer, split fuel costs by type, and track daily cash flows.",
            },
            "Q7_incorporate_before_simulator": {
                "answer": "1) Validate km: odometer (closes) vs km_recorrido (billing) vs distancia_km (trips). 2) Split fuel: GNV vs gasoline from closes. 3) Add daily settlement tracking to P2 UI.",
                "reason": "These are low-risk additions that increase data confidence before building a simulator.",
            },
            "Q8_ready_for_p3": {
                "answer": "CONDITIONAL -- serving facts are solid for module_weekly_billing. But vehicle assignment is missing, and module_driver_closes is untapped.",
                "reason": "P3 Scenario Engine needs per-vehicle profitability which requires vehicle-driver assignment. Without it, simulations are driver-only.",
            },
        }

        for qid, v in verdicts.items():
            print(f"\n  {qid}:")
            print(f"    ANSWER: {v['answer']}")
            print(f"    REASON: {v['reason']}")

        print(f"\n  FINDINGS ({len(findings)}):")
        for f in findings:
            print(f"    {f}")

        cur.close()

    print("\n" + "=" * 70)
    print("RECONCILIATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run()
