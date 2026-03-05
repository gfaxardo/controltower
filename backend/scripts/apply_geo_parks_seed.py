#!/usr/bin/env python3
"""
Aplica backend/seeds/geo_parks_seed.sql para actualizar city/country en dim.dim_geo_park.
Imprime cuántos parks quedan con city o country = 'UNKNOWN'.
Uso: cd backend && python -m scripts.apply_geo_parks_seed
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from app.db.connection import init_db_pool, get_db

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    seed_path = os.path.join(base, "seeds", "geo_parks_seed.sql")
    if not os.path.isfile(seed_path):
        print(f"[ERROR] No encontrado: {seed_path}")
        return 1

    with open(seed_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Ejecutar solo sentencias UPDATE/INSERT/SELECT que no sean solo comentarios
    statements = [
        s.strip() for s in content.split(";")
        if s.strip() and not s.strip().startswith("--") and (s.strip().upper().startswith("UPDATE") or s.strip().upper().startswith("INSERT") or s.strip().upper().startswith("SELECT"))
    ]

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        for stmt in statements:
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    print(f"[WARN] {e}: {stmt[:80]}...")
        # Contar UNKNOWN
        cur.execute("""
            SELECT COUNT(*) AS n
            FROM dim.dim_geo_park
            WHERE city = 'UNKNOWN' OR country = 'UNKNOWN'
        """)
        n_unknown = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) AS n FROM dim.dim_geo_park")
        n_total = cur.fetchone()[0]
        cur.close()

    print(f"Parks con city o country = UNKNOWN: {n_unknown} / {n_total}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
