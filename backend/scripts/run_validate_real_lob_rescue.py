"""
Ejecuta validate_real_lob_rescue.sql usando la conexión de la app (sin psql).
- Freshness (v_real_freshness_trips) hace full scan sobre canon (~55M filas): timeout 20min.
- Uso: python -m scripts.run_validate_real_lob_rescue
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

SQL_PATH = os.path.join(BACKEND_DIR, "scripts", "sql", "validate_real_lob_rescue.sql")

# Timeout por defecto (freshness puede tardar mucho sobre v_trips_real_canon)
DEFAULT_STATEMENT_TIMEOUT = "20min"
# Solo para el paso de Freshness (paso 5)
FRESHNESS_STATEMENT_TIMEOUT = "30min"


def main():
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    with open(SQL_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    # Dividir por ; (ignorar comentarios de bloque y líneas vacías)
    statements = []
    for block in sql.split(";"):
        lines = [l for l in block.split("\n") if l.strip() and not l.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SET statement_timeout = '{DEFAULT_STATEMENT_TIMEOUT}'")
        for i, stmt in enumerate(statements):
            # Paso 5 = Freshness: aumentar timeout solo para ese SELECT
            if "v_real_freshness_trips" in stmt and "SELECT" in stmt:
                cur.execute(f"SET statement_timeout = '{FRESHNESS_STATEMENT_TIMEOUT}'")
            try:
                cur.execute(stmt)
                rows = cur.fetchall()
                if rows:
                    first = rows[0]
                    keys = list(first.keys()) if hasattr(first, "keys") else []
                    if "paso" in keys:
                        print(f"\n--- {first.get('paso', '')} ---")
                        if len(rows) > 1:
                            for r in rows[1:]:
                                print(dict(r))
                        elif len(keys) > 1:
                            print(dict(first))
                    else:
                        for r in rows:
                            print(dict(r))
            except Exception as e:
                print(f"Error ejecutando: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
            finally:
                if "v_real_freshness_trips" in stmt and "SELECT" in stmt:
                    cur.execute(f"SET statement_timeout = '{DEFAULT_STATEMENT_TIMEOUT}'")
        cur.close()


if __name__ == "__main__":
    main()
