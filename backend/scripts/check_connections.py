#!/usr/bin/env python3
"""Imprime dos lineas: activas, max_connections. Usado por el bloque de cierre Fase 2B."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("0\n100")
        return 1
    try:
        import psycopg2
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("""
            SELECT (SELECT count(*) FROM pg_stat_activity), (SELECT setting::int FROM pg_settings WHERE name = 'max_connections')
        """)
        r = cur.fetchone()
        cur.close()
        conn.close()
        print(r[0])
        print(r[1])
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("0\n100")  # fallback para que el bloque PowerShell pueda parsear
        return 1

if __name__ == "__main__":
    sys.exit(main())
