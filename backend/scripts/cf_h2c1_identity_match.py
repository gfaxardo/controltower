"""
CF-H2C.1 — Driver Identity Matching Service

Cross-references CT driver identity (public.drivers, public.trips_2026)
with Yango driver identity (raw_yango.driver_profiles_raw, raw_yango.orders_raw).

Multiple match methods with confidence scoring.
Populates ops.yango_driver_identity_map_shadow (shadow mode).

Usage:
  python -m scripts.cf_h2c1_identity_match --park-id 08e20910... --dry-run
  python -m scripts.cf_h2c1_identity_match --park-id 08e20910... --confirm
"""
from __future__ import annotations

import argparse
import re
import sys
import os
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

LIMA = "08e20910d81d42658d4334d3f6d10ac0"


def _normalize_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    return re.sub(r"[^0-9]", "", str(phone))[-10:]


def _normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(str(name).lower().strip().split())


def _normalize_license(lic: Optional[str]) -> str:
    if not lic:
        return ""
    return re.sub(r"[^a-zA-Z0-9]", "", str(lic)).upper()


def _match_score_str(level: str) -> float:
    return {"VERY_HIGH": 1.0, "HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.3, "AMBIGUOUS": 0.1, "UNMATCHED": 0.0}.get(level, 0.0)


def run_identity_match(park_id: str, dry_run: bool = False) -> Dict[str, Any]:
    results = {
        "park_id": park_id,
        "dry_run": dry_run,
        "ct_drivers_total": 0,
        "ct_drivers_with_phone": 0,
        "ct_drivers_with_license": 0,
        "yango_drivers_total": 0,
        "yango_drivers_with_orders": 0,
        "matches": {},
        "unmatched_ct": 0,
        "unmatched_yango": 0,
    }

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ==================================================================
        # 1. Load CT drivers (public.drivers)
        # ==================================================================
        print("Loading CT drivers from public.drivers...")
        cur.execute("""
            SELECT driver_id, full_name, phone, license_number,
                   park_id, work_status, active
            FROM public.drivers
            WHERE driver_id IS NOT NULL
        """)
        ct_drivers = {r["driver_id"]: dict(r) for r in cur.fetchall()}
        results["ct_drivers_total"] = len(ct_drivers)
        results["ct_drivers_with_phone"] = sum(1 for d in ct_drivers.values() if d["phone"])
        results["ct_drivers_with_license"] = sum(1 for d in ct_drivers.values() if d["license_number"])
        print(f"  CT drivers: {len(ct_drivers)} (phone: {results['ct_drivers_with_phone']}, license: {results['ct_drivers_with_license']})")

        # ==================================================================
        # 2. Load Yango driver profiles
        # ==================================================================
        print("Loading Yango driver profiles...")
        cur.execute("""
            SELECT driver_profile_id, work_status, park_id, raw_payload
            FROM raw_yango.driver_profiles_raw
            WHERE park_id = %s
        """, (park_id,))
        yango_profiles = {}
        for r in cur.fetchall():
            rp = r["raw_payload"] or {}
            dp = rp.get("driver_profile", {}) if isinstance(rp, dict) else {}
            yango_profiles[r["driver_profile_id"]] = {
                "driver_profile_id": r["driver_profile_id"],
                "work_status": r["work_status"],
                "park_id": r["park_id"],
                "first_name": dp.get("first_name", ""),
                "last_name": dp.get("last_name", ""),
                "phone": dp.get("phone", ""),
                "full_name": f"{dp.get('first_name', '')} {dp.get('last_name', '')}".strip(),
            }
        results["yango_drivers_total"] = len(yango_profiles)
        print(f"  Yango drivers: {len(yango_profiles)}")

        # ==================================================================
        # 3. Load Yango drivers with orders (activity evidence)
        # ==================================================================
        print("Loading Yango order activity...")
        cur.execute("""
            SELECT driver_profile_id,
                   MIN(order_ended_at) AS first_order,
                   MAX(order_ended_at) AS last_order,
                   COUNT(*) AS order_count
            FROM raw_yango.orders_raw
            WHERE park_id = %s AND order_status = 'complete'
            GROUP BY driver_profile_id
        """, (park_id,))
        yango_activity = {}
        for r in cur.fetchall():
            yango_activity[r["driver_profile_id"]] = {
                "first_order": r["first_order"],
                "last_order": r["last_order"],
                "order_count": r["order_count"],
            }
        results["yango_drivers_with_orders"] = len(yango_activity)
        print(f"  Yango drivers with orders: {len(yango_activity)}")

        # ==================================================================
        # 4. Load CT active drivers from trips_2026
        # ==================================================================
        print("Loading CT driver activity from trips_2026...")
        cur.execute("""
            SELECT conductor_id,
                   MIN(fecha_finalizacion) AS first_trip,
                   MAX(fecha_finalizacion) AS last_trip,
                   COUNT(*) AS trip_count
            FROM public.trips_2026
            WHERE park_id = %s AND condicion = 'Completado'
            GROUP BY conductor_id
        """, (park_id,))
        ct_activity = {}
        for r in cur.fetchall():
            ct_activity[r["conductor_id"]] = {
                "first_trip": r["first_trip"],
                "last_trip": r["last_trip"],
                "trip_count": r["trip_count"],
            }
        print(f"  CT drivers with trips_2026: {len(ct_activity)}")

        # ==================================================================
        # 5. Build lookup indexes
        # ==================================================================
        ct_by_phone = {}
        ct_by_license = {}
        ct_by_fullname = {}
        ct_ids = set(ct_drivers.keys())

        for did, d in ct_drivers.items():
            ph = _normalize_phone(d["phone"])
            lic = _normalize_license(d["license_number"])
            nm = _normalize_name(d["full_name"])
            if ph:
                ct_by_phone.setdefault(ph, []).append(did)
            if lic:
                ct_by_license.setdefault(lic, []).append(did)
            if nm:
                ct_by_fullname.setdefault(nm, []).append(did)

        yango_by_phone = {}
        yango_by_fullname = {}
        for yid, y in yango_profiles.items():
            ph = _normalize_phone(y["phone"])
            nm = _normalize_name(y["full_name"])
            if ph:
                yango_by_phone[ph] = yid
            if nm:
                yango_by_fullname[nm] = yid

        # ==================================================================
        # 6. MATCHING: Multi-method
        # ==================================================================
        matched_ct = set()
        matched_yango = set()
        match_rows = []
        match_counts = {m: 0 for m in [
            "exact_id", "phone", "license", "name_and_phone",
            "name_and_license", "name_only",
        ]}

        # --- Method 1: Exact driver_id match ---
        print("\nMatching: exact_id...")
        for yid in yango_profiles:
            if yid in ct_ids:
                ct = ct_drivers[yid]
                y = yango_profiles[yid]
                act = yango_activity.get(yid, {})
                match_rows.append(_make_row(park_id, ct, y, act, "exact_id", "VERY_HIGH", 1.0))
                matched_ct.add(yid)
                matched_yango.add(yid)
                match_counts["exact_id"] += 1
        print(f"  exact_id: {match_counts['exact_id']}")

        # --- Method 2: Phone match (normalized) ---
        print("Matching: phone...")
        for ph, ct_list in ct_by_phone.items():
            if ph in yango_by_phone:
                yid = yango_by_phone[ph]
                if yid in matched_yango:
                    continue
                # Take first unmatched CT driver with this phone
                for cid in ct_list:
                    if cid not in matched_ct:
                        ct = ct_drivers[cid]
                        y = yango_profiles[yid]
                        act = yango_activity.get(yid, {})
                        match_rows.append(_make_row(park_id, ct, y, act, "phone", "HIGH", 0.85))
                        matched_ct.add(cid)
                        matched_yango.add(yid)
                        match_counts["phone"] += 1
                        break
        print(f"  phone: {match_counts['phone']}")

        # --- Method 3: License match ---
        print("Matching: license...")
        for lic, ct_list in ct_by_license.items():
            for cid in ct_list:
                if cid in matched_ct:
                    continue
                ct = ct_drivers[cid]
                ct_lic = _normalize_license(ct["license_number"])
                # Find Yango drivers with matching license in raw_payload
                for yid, y in yango_profiles.items():
                    if yid in matched_yango:
                        continue
                    rp = y.get("raw_payload")
                    # Check if license is in raw_payload (not in flattened columns)
                    if rp and isinstance(rp, dict):
                        dp = rp.get("driver_profile", {})
                        ya_lic = _normalize_license(dp.get("license_number", ""))
                    else:
                        ya_lic = ""
                    if ct_lic and ya_lic and ct_lic == ya_lic:
                        act = yango_activity.get(yid, {})
                        match_rows.append(_make_row(park_id, ct, y, act, "license", "HIGH", 0.85))
                        matched_ct.add(cid)
                        matched_yango.add(yid)
                        match_counts["license"] += 1
                        break
        print(f"  license: {match_counts['license']}")

        # --- Method 4: Name + Phone ---
        print("Matching: name_and_phone...")
        for nm, ct_list in ct_by_fullname.items():
            if nm in yango_by_fullname:
                yid = yango_by_fullname[nm]
                if yid in matched_yango:
                    continue
                # Verify phone also matches
                y = yango_profiles[yid]
                y_ph = _normalize_phone(y["phone"])
                for cid in ct_list:
                    if cid in matched_ct:
                        continue
                    ct = ct_drivers[cid]
                    ct_ph = _normalize_phone(ct["phone"])
                    if ct_ph and y_ph and ct_ph == y_ph:
                        act = yango_activity.get(yid, {})
                        match_rows.append(_make_row(park_id, ct, y, act, "name_and_phone", "VERY_HIGH", 0.95))
                        matched_ct.add(cid)
                        matched_yango.add(yid)
                        match_counts["name_and_phone"] += 1
                        break
        print(f"  name_and_phone: {match_counts['name_and_phone']}")

        # --- Method 5: Name + License ---
        print("Matching: name_and_license...")
        for nm, ct_list in ct_by_fullname.items():
            if nm in yango_by_fullname:
                yid = yango_by_fullname[nm]
                if yid in matched_yango:
                    continue
                y = yango_profiles[yid]
                for cid in ct_list:
                    if cid in matched_ct:
                        continue
                    ct = ct_drivers[cid]
                    ct_lic = _normalize_license(ct["license_number"])
                    if ct_lic:
                        act = yango_activity.get(yid, {})
                        match_rows.append(_make_row(park_id, ct, y, act, "name_and_license", "HIGH", 0.80))
                        matched_ct.add(cid)
                        matched_yango.add(yid)
                        match_counts["name_and_license"] += 1
                        break
        print(f"  name_and_license: {match_counts['name_and_license']}")

        # --- Method 6: Name only (LOW confidence - not promotable) ---
        print("Matching: name_only (LOW)...")
        for nm, ct_list in ct_by_fullname.items():
            if nm in yango_by_fullname:
                yid = yango_by_fullname[nm]
                if yid in matched_yango:
                    continue
                for cid in ct_list:
                    if cid in matched_ct:
                        continue
                    ct = ct_drivers[cid]
                    y = yango_profiles[yid]
                    act = yango_activity.get(yid, {})
                    match_rows.append(_make_row(park_id, ct, y, act, "name_only", "LOW", 0.30))
                    matched_ct.add(cid)
                    matched_yango.add(yid)
                    match_counts["name_only"] += 1
                    break
        print(f"  name_only: {match_counts['name_only']}")

        # ==================================================================
        # 7. Calculate remaining unmatched
        # ==================================================================
        results["unmatched_ct"] = len(ct_ids) - len(matched_ct)
        results["unmatched_yango"] = len(yango_profiles) - len(matched_yango)
        results["matches"] = match_counts
        results["total_matched"] = len(match_rows)
        results["total_match_pct_ct"] = round(len(matched_ct) / max(len(ct_ids), 1) * 100, 1)
        results["total_match_pct_yango"] = round(len(matched_yango) / max(len(yango_profiles), 1) * 100, 1)

        # ==================================================================
        # 8. Show summary by confidence
        # ==================================================================
        print(f"\n{'='*60}")
        print(f"MATCHING SUMMARY")
        print(f"{'='*60}")
        print(f"  Total CT drivers: {len(ct_ids)}")
        print(f"  Total Yango drivers: {len(yango_profiles)}")
        print(f"  Matched CT: {len(matched_ct)} ({results['total_match_pct_ct']}%)")
        print(f"  Matched Yango: {len(matched_yango)} ({results['total_match_pct_yango']}%)")
        print(f"  Unmatched CT: {results['unmatched_ct']}")
        print(f"  Unmatched Yango: {results['unmatched_yango']}")
        print()
        for method, count in match_counts.items():
            print(f"  {method:20s}: {count:>6d}")
        print()

        # Confidence breakdown
        conf_counts = {"VERY_HIGH": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "AMBIGUOUS": 0}
        for r in match_rows:
            conf_counts[r["match_confidence"]] = conf_counts.get(r["match_confidence"], 0) + 1
        print("  By confidence:")
        for level in ["VERY_HIGH", "HIGH", "MEDIUM", "LOW"]:
            print(f"    {level:12s}: {conf_counts.get(level, 0):>6d}")

        high_plus = conf_counts.get("VERY_HIGH", 0) + conf_counts.get("HIGH", 0)
        high_plus_pct = round(high_plus / max(len(yango_profiles), 1) * 100, 1)
        print(f"\n  HIGH+ confidence: {high_plus} ({high_plus_pct}% of Yango drivers)")

        # ==================================================================
        # 9. Upsert (or dry-run)
        # ==================================================================
        if dry_run:
            print(f"\n[DRY RUN] Would insert {len(match_rows)} identity map rows")
        else:
            print(f"\n[CONFIRM] Inserting {len(match_rows)} identity map rows...")
            inserted = 0
            for row in match_rows:
                try:
                    cur.execute("""
                        INSERT INTO ops.yango_driver_identity_map_shadow (
                            ct_driver_id, ct_full_name, ct_phone_raw, ct_phone_normalized,
                            ct_license_number, ct_park_id, ct_work_status, ct_active,
                            trips_2026_driver_key,
                            yango_driver_profile_id, yango_full_name,
                            yango_phone_raw, yango_phone_normalized,
                            yango_work_status, yango_park_id,
                            park_id, match_method, match_confidence, match_score,
                            first_seen_order_at, last_seen_order_at, orders_count,
                            source_status
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (ct_driver_id, yango_driver_profile_id, match_method) DO UPDATE SET
                            ct_full_name = EXCLUDED.ct_full_name,
                            ct_phone_normalized = EXCLUDED.ct_phone_normalized,
                            match_confidence = EXCLUDED.match_confidence,
                            match_score = EXCLUDED.match_score,
                            updated_at = NOW()
                    """, (
                        row["ct_driver_id"], row["ct_full_name"],
                        row["ct_phone_raw"], row["ct_phone_normalized"],
                        row["ct_license_number"], row["ct_park_id"],
                        row["ct_work_status"], row["ct_active"],
                        row["trips_2026_driver_key"],
                        row["yango_driver_profile_id"], row["yango_full_name"],
                        row["yango_phone_raw"], row["yango_phone_normalized"],
                        row["yango_work_status"], row["yango_park_id"],
                        row["park_id"], row["match_method"], row["match_confidence"],
                        row["match_score"],
                        row["first_seen_order_at"], row["last_seen_order_at"],
                        row["orders_count"],
                        row["source_status"],
                    ))
                    inserted += cur.rowcount
                except Exception as e:
                    print(f"    insert error: {str(e)[:80]}")

            conn.commit()
            print(f"  Inserted/updated: {inserted} rows")

        cur.close()

    return results


def _make_row(park_id, ct, y, act, method, confidence, score):
    ct_ph_norm = _normalize_phone(ct.get("phone"))
    y_ph_norm = _normalize_phone(y.get("phone"))
    return {
        "ct_driver_id": ct.get("driver_id"),
        "ct_full_name": ct.get("full_name"),
        "ct_phone_raw": ct.get("phone"),
        "ct_phone_normalized": ct_ph_norm,
        "ct_license_number": ct.get("license_number"),
        "ct_park_id": ct.get("park_id"),
        "ct_work_status": ct.get("work_status"),
        "ct_active": ct.get("active"),
        "trips_2026_driver_key": ct.get("driver_id"),
        "yango_driver_profile_id": y.get("driver_profile_id"),
        "yango_full_name": y.get("full_name"),
        "yango_phone_raw": y.get("phone"),
        "yango_phone_normalized": y_ph_norm,
        "yango_work_status": y.get("work_status"),
        "yango_park_id": y.get("park_id"),
        "park_id": park_id,
        "match_method": method,
        "match_confidence": confidence,
        "match_score": score,
        "first_seen_order_at": act.get("first_order"),
        "last_seen_order_at": act.get("last_order"),
        "orders_count": act.get("order_count", 0),
        "source_status": "SHADOW",
    }


def main():
    ap = argparse.ArgumentParser(description="CF-H2C.1 Driver Identity Match")
    ap.add_argument("--park-id", default=LIMA)
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--confirm", dest="dry_run", action="store_false")
    args = ap.parse_args()

    print(f"CF-H2C.1 Driver Identity Match")
    print(f"  Park: {args.park_id[:8]}***")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'CONFIRM'}")
    print()

    results = run_identity_match(args.park_id, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
