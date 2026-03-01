#!/usr/bin/env python3
"""
Ejecuta: 1) driver_lifecycle_build.sql  2) refresh_driver_lifecycle_mvs()  3) validaciones.
Uso: cd backend && python -m scripts.run_driver_lifecycle_build
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor


def split_sql(content: str):
    """Divide SQL en sentencias; no parte dentro de bloques $$ ... $$."""
    content = re.sub(r"--[^\n]*", "", content)
    statements = []
    buf = []
    inside_dollar = False
    i = 0
    n = len(content)
    while i < n:
        if not inside_dollar and content[i:i + 2] == "$$":
            inside_dollar = True
            buf.append(content[i:i + 2])
            i += 2
            continue
        if inside_dollar and content[i:i + 2] == "$$":
            inside_dollar = False
            buf.append(content[i:i + 2])
            i += 2
            continue
        if not inside_dollar and content[i] == ";" and (i + 1 >= n or content[i + 1] in "\n\r"):
            j = i + 1
            while j < n and content[j] in " \t\n\r":
                j += 1
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i = j
            continue
        buf.append(content[i])
        i += 1
    stmt = "".join(buf).strip()
    if stmt:
        statements.append(stmt)
    return statements


def run_build():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql_path = os.path.join(base, "sql", "driver_lifecycle_build.sql")
    if not os.path.isfile(sql_path):
        print(f"[ERROR] No encontrado: {sql_path}")
        return False
    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()
    statements = split_sql(content)
    print(f"[INFO] {len(statements)} sentencias a ejecutar.")
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '7200000'")  # 2h en ms
        for i, stmt in enumerate(statements):
            if not stmt or len(stmt) < 3:
                continue
            try:
                cur.execute(stmt)
                conn.commit()
                name = stmt[:60].replace("\n", " ") + ("..." if len(stmt) > 60 else "")
                print(f"  OK [{i+1}] {name}")
            except Exception as e:
                conn.rollback()
                print(f"  ERROR [{i+1}] {e}")
                print(f"  Stmt: {stmt[:200]}...")
                return False
        cur.close()
    return True


def run_refresh():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '7200000'")
        try:
            cur.execute("SELECT ops.refresh_driver_lifecycle_mvs()")
            conn.commit()
            print("[OK] refresh_driver_lifecycle_mvs() ejecutado.")
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] refresh: {e}")
            return False
        cur.close()
    return True


def run_validations():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql_path = os.path.join(base, "sql", "driver_lifecycle_validations.sql")
    if not os.path.isfile(sql_path):
        print(f"[WARN] No encontrado: {sql_path}")
        return True
    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Quitar comentarios y dividir por ;
    content = re.sub(r"--[^\n]*", "", content)
    queries = [q.strip() for q in re.split(r";\s*\n", content) if q.strip() and "SELECT" in q.upper()]
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = '120000'")
        for i, q in enumerate(queries):
            if not q.strip():
                continue
            try:
                cur.execute(q)
                rows = cur.fetchall()
                print(f"\n--- Validación {i+1} ---")
                for r in rows:
                    print(dict(r))
            except Exception as e:
                print(f"[ERROR] Validación {i+1}: {e}")
        cur.close()
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("1) Build driver_lifecycle_build.sql")
    print("=" * 60)
    if not run_build():
        sys.exit(1)
    print("\n" + "=" * 60)
    print("2) Refresh MVs: ops.refresh_driver_lifecycle_mvs()")
    print("=" * 60)
    if not run_refresh():
        sys.exit(1)
    print("\n" + "=" * 60)
    print("3) Validaciones")
    print("=" * 60)
    run_validations()
    print("\nListo.")
