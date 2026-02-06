"""
[YEGO CT] PASO 3A E2E — Construir plan.plan_lob_long + poblar ops.lob_catalog desde staging.
Ejecuta SQL (schema, tabla, truncate, insert, lob_catalog) y validaciones rápidas.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
PASO3A_SQL = os.path.join(SQL_DIR, "paso3a_plan_lob_long_and_catalog.sql")


def main():
    init_db_pool()

    if not os.path.exists(PASO3A_SQL):
        print(f"[ERROR] No encontrado: {PASO3A_SQL}")
        sys.exit(1)

    with open(PASO3A_SQL, "r", encoding="utf-8") as f:
        lines = f.readlines()
    content = "\n".join(
        line[: line.index("--")].strip() if "--" in line else line.strip()
        for line in lines
    )
    statements = [s.strip() for s in content.split(";") if s.strip()]

    print("=== PASO 3A — Ejecutando SQL ===\n")
    with get_db() as conn:
        cur = conn.cursor()
        for st in statements:
            if not st:
                continue
            try:
                cur.execute(st)
                conn.commit()
            except Exception as e:
                print(f"  [ERROR] {e}")
                conn.rollback()
        cur.close()

    print("  SQL ejecutado.\n")

    print("=== Validaciones rápidas ===\n")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM plan.plan_lob_long")
        plan_rows = cur.fetchone()[0]
        print(f"  plan_rows (plan.plan_lob_long): {plan_rows}")
        cur.execute("SELECT MIN(period_date), MAX(period_date) FROM plan.plan_lob_long")
        r = cur.fetchone()
        if r and r[0]:
            print(f"  period_date: {r[0]} .. {r[1]}")
        cur.execute("SELECT COUNT(*) FROM ops.lob_catalog WHERE source='plan'")
        lob_catalog_plan = cur.fetchone()[0]
        print(f"  lob_catalog_plan (source='plan'): {lob_catalog_plan}")
        cur.execute("""
            SELECT country, city, lob_name, COUNT(*)
            FROM ops.lob_catalog
            WHERE source='plan'
            GROUP BY 1,2,3
            ORDER BY 4 DESC
            LIMIT 50
        """)
        rows = cur.fetchall()
        if rows:
            print("  Top country, city, lob_name:")
            for row in rows[:15]:
                print(f"    {row[0]} | {row[1]} | {row[2]} | {row[3]}")
            if len(rows) > 15:
                print(f"    ... y {len(rows)-15} más")
        cur.close()

    print("\n" + "="*50)
    if plan_rows > 0 and lob_catalog_plan > 0:
        print("  PASO 3A OK")
    else:
        print("  PASO 3A: fallo (plan_rows o lob_catalog_plan en 0)")
    print("="*50)


if __name__ == "__main__":
    main()
