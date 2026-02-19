"""
Inspección rápida DB para PASO 4: trips_all, parks, match park_id.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool


def run():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '30s'")
        cur.execute("SELECT COUNT(*) FROM public.trips_all")
        n_trips = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT park_id) FROM public.trips_all")
        n_distinct_park = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM public.parks")
        n_parks = cur.fetchone()[0]
        cur.execute("SELECT id, name, city, created_at FROM public.parks LIMIT 20")
        parks_sample = cur.fetchall()
        cur.close()

    print("=== Inspección DB ===\n")
    print(f"  COUNT(*) trips_all:           {n_trips}")
    print(f"  COUNT(DISTINCT park_id) trips: {n_distinct_park}")
    print(f"  COUNT(*) parks:                {n_parks}")
    print("\n  parks LIMIT 20 (id, name, city, created_at):")
    for r in parks_sample:
        print(f"    {r}")
    print("\n  (Confirmar: parks.id matchea trips_all.park_id)\n")


if __name__ == "__main__":
    run()
