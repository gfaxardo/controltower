#!/usr/bin/env python3
"""Imprime COUNT(*), MIN(week_start), MAX(week_start) de ops.mv_real_trips_weekly (una linea tab-separada)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("0\t\t", end="")
        return 1
    try:
        import psycopg2
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), MIN(week_start)::text, MAX(week_start)::text FROM ops.mv_real_trips_weekly")
        r = cur.fetchone()
        cur.close()
        conn.close()
        print(f"{r[0] or 0}\t{r[1] or ''}\t{r[2] or ''}")
        return 0
    except Exception as e:
        print(f"0\t\t", end="", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
