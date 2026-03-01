#!/usr/bin/env python3
"""Aplica driver_lifecycle_refresh_hardening.sql (CREATE OR REPLACE de las funciones)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool


def split_sql(content: str):
    """Divide SQL en sentencias; no parte dentro de bloques $$ ... $$."""
    content = re.sub(r"--[^\n]*", "", content)
    statements = []
    buf = []
    inside_dollar = False
    i = 0
    n = len(content)
    while i < n:
        if not inside_dollar and content[i : i + 2] == "$$":
            inside_dollar = True
            buf.append(content[i : i + 2])
            i += 2
            continue
        if inside_dollar and content[i : i + 2] == "$$":
            inside_dollar = False
            buf.append(content[i : i + 2])
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


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "sql", "driver_lifecycle_refresh_hardening.sql")
    if not os.path.isfile(path):
        print(f"ERROR: No encontrado {path}")
        return 1
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    statements = split_sql(content)
    print(f"Aplicando {len(statements)} sentencias desde driver_lifecycle_refresh_hardening.sql")
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        for i, stmt in enumerate(statements):
            if not stmt or len(stmt) < 10:
                continue
            try:
                cur.execute(stmt)
                conn.commit()
                name = stmt.split()[2:5]  # e.g. FUNCTION ops.refresh_driver_lifecycle_mvs
                print(f"  OK: {' '.join(name)}")
            except Exception as e:
                conn.rollback()
                print(f"  ERROR: {e}")
                return 1
        cur.close()
    print("Hardening aplicado correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
