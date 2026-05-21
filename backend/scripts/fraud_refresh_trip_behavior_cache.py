"""Fase 1F-8 — Trip Behavior Feature Cache Refresh.

Puebla fraud.trip_behavior_feature_cache con datos D-30 desde public.trips_2026.
Procesa viajes en batches, parsea rutas y construye cluster keys.

Uso:
    python fraud_refresh_trip_behavior_cache.py --date-from 2026-04-20 --date-to 2026-05-20 --dry-run true
    python fraud_refresh_trip_behavior_cache.py --date-from 2026-04-20 --date-to 2026-05-20 --dry-run false --batch-size 1000
"""
import sys, os, time, argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from app.services.fraud.fraud_route_parser import (
    parse_route_text, build_origin_cluster_key, build_destination_cluster_key,
    build_route_signature, build_reverse_route_signature,
)
from psycopg2.extras import execute_values

SOURCE_TABLE = "public.trips_2026"


def refresh_cache(date_from, date_to, dry_run=True, batch_size=1000, limit=None):
    print(f"=== TRIP BEHAVIOR FEATURE CACHE REFRESH (F1F-8) ===")
    print(f"  Date range: {date_from} -> {date_to}")
    print(f"  Batch size: {batch_size}")
    print(f"  Dry run: {dry_run}")
    if limit:
        print(f"  Limit: {limit}")

    # Ensure date_to is inclusive (+1 day)
    if isinstance(date_to, str):
        date_to_dt = datetime.strptime(date_to, "%Y-%m-%d")
        date_to_exclusive = (date_to_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        date_to_exclusive = (date_to + timedelta(days=1)).strftime("%Y-%m-%d") if hasattr(date_to, 'strftime') else date_to

    # Count total rows
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM public.trips_2026
            WHERE condicion = 'Completado'
              AND fecha_inicio_viaje >= %s
              AND fecha_inicio_viaje < %s
        """, (date_from, date_to_exclusive))
        total_rows = cur.fetchone()[0] or 0
        cur.close()

    print(f"  Rows scanned: {total_rows}")

    if total_rows == 0:
        print("  No trips found in range. Exiting.")
        return {"rows_scanned": 0, "rows_inserted": 0, "dry_run": dry_run}

    batches = (total_rows + batch_size - 1) // batch_size
    if limit:
        batches = min(batches, (limit + batch_size - 1) // batch_size)

    total_processed = 0
    total_inserted = 0
    total_duplicates = 0
    total_elapsed = 0

    for batch_num in range(batches):
        offset = batch_num * batch_size
        effective_limit = min(batch_size, total_rows - offset)
        if limit and total_processed >= limit:
            break

        print(f"\n  Batch {batch_num+1}/{batches} (offset {offset}, limit {effective_limit})")
        t0 = time.time()

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT conductor_id, park_id, codigo_pedido, fecha_inicio_viaje,
                       direccion, precio_yango_pro, distancia_km,
                       EXTRACT(EPOCH FROM (fecha_finalizacion - fecha_inicio_viaje)) AS duration_s
                FROM public.trips_2026
                WHERE condicion = 'Completado'
                  AND fecha_inicio_viaje >= %s
                  AND fecha_inicio_viaje < %s
                ORDER BY fecha_inicio_viaje, codigo_pedido
                LIMIT %s OFFSET %s
            """, (date_from, date_to_exclusive, effective_limit, offset))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            cur.close()

        cache_rows = []
        for row in rows:
            d = dict(zip(columns, row))
            trip_id = str(d["codigo_pedido"]) if d["codigo_pedido"] else None
            driver_id = str(d["conductor_id"]) if d["conductor_id"] else None
            if not trip_id or not driver_id:
                continue

            route_text = d["direccion"]
            route_info = parse_route_text(route_text)

            row_dict = {
                "pickup_lat": None, "pickup_lng": None,
                "dropoff_lat": None, "dropoff_lng": None,
                "origin_norm": route_info["origin_norm"],
                "destination_norm": route_info["destination_norm"],
                "route_signature": route_info["route_signature"],
                "reverse_route_signature": route_info["reverse_route_signature"],
            }
            origin_key = build_origin_cluster_key(row_dict)
            dest_key = build_destination_cluster_key(row_dict)
            route_sig = route_info["route_signature"] or build_route_signature(row_dict)
            rev_sig = route_info["reverse_route_signature"] or build_reverse_route_signature(row_dict)

            cache_rows.append((
                SOURCE_TABLE,
                trip_id,
                driver_id,
                str(d["park_id"]) if d.get("park_id") is not None else None,
                d["fecha_inicio_viaje"],
                origin_key,
                dest_key,
                route_sig,
                rev_sig,
                float(d["precio_yango_pro"]) if d.get("precio_yango_pro") is not None else None,
                float(d["distancia_km"]) if d.get("distancia_km") is not None else None,
                float(d["duration_s"]) if d.get("duration_s") is not None else None,
            ))

        total_processed += len(rows)

        if not dry_run and cache_rows:
            with get_db() as conn:
                cur = conn.cursor()
                execute_values(cur, """
                    INSERT INTO fraud.trip_behavior_feature_cache
                        (source_table, source_trip_id, driver_id, park_id, trip_datetime,
                         origin_cluster_key, destination_cluster_key,
                         route_signature, reverse_route_signature,
                         amount, distance, duration)
                    VALUES %s
                    ON CONFLICT (source_table, source_trip_id) DO NOTHING
                """, cache_rows)
                inserted = cur.rowcount
                duplicates = len(cache_rows) - inserted
                total_inserted += inserted
                total_duplicates += duplicates
                conn.commit()
                cur.close()
        else:
            total_inserted += len(cache_rows)
            total_duplicates = 0

        elapsed = round(time.time() - t0, 1)
        total_elapsed += elapsed
        print(f"    -> {len(cache_rows)} parsed, {len(cache_rows)} rows to upsert in {elapsed}s")

    print(f"\n=== CACHE REFRESH COMPLETE ===")
    print(f"  Rows scanned: {total_processed}")
    print(f"  Rows inserted/upserted: {total_inserted}")
    print(f"  Duplicates skipped: {total_duplicates}")
    print(f"  Total elapsed: {total_elapsed}s ({round(total_elapsed/60,1)} min)")
    if dry_run:
        print("  [DRY RUN] No data written.")

    return {
        "rows_scanned": total_processed,
        "rows_inserted": total_inserted,
        "duplicates_skipped": total_duplicates,
        "elapsed_seconds": total_elapsed,
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh trip behavior feature cache D-30 (F1F-8)")
    parser.add_argument("--date-from", type=str, required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--date-to", type=str, required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--limit", type=int, default=None, help="Max total rows (for testing)")
    args = parser.parse_args()

    dry = args.dry_run.lower() in ("true", "1", "yes")
    refresh_cache(
        date_from=args.date_from,
        date_to=args.date_to,
        dry_run=dry,
        batch_size=args.batch_size,
        limit=args.limit,
    )
