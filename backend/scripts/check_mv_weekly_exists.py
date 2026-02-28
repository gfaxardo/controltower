#!/usr/bin/env python3
"""Comprueba si existe ops.mv_real_trips_weekly. Imprime 'yes' o 'no' (una linea)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname='ops' AND matviewname='mv_real_trips_weekly')"
        )
        exists = cur.fetchone()[0]
    print("yes" if exists else "no")

if __name__ == "__main__":
    main()
