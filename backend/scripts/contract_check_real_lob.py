#!/usr/bin/env python3
"""
Contract check: REAL LOB Observability.
- Valida que existan vistas y tablas: ops.v_real_trips_by_lob_month, ops.v_real_trips_by_lob_week,
  canon.dim_lob, canon.map_real_to_lob, ops.v_real_universe_with_lob.
- Valida que no haya mezcla con Plan (las vistas no deben depender de ops.v_plan_vs_real_realkey_final).
- Opcional: vistas no vacías (warning si están vacías).
Exit 0 si OK, exit 1 si falla.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)
try:
    from dotenv import load_dotenv
    if os.path.isfile(os.path.join(BACKEND_DIR, ".env")):
        load_dotenv(os.path.join(BACKEND_DIR, ".env"))
except ImportError:
    pass

from app.db.connection import get_db, init_db_pool

REQUIRED_VIEWS = [
    ("ops", "v_real_trips_by_lob_month"),
    ("ops", "v_real_trips_by_lob_week"),
    ("ops", "v_real_universe_with_lob"),
]
REQUIRED_TABLES = [
    ("canon", "dim_lob"),
    ("canon", "map_real_to_lob"),
]
FORBIDDEN_VIEW_DEPENDENCY = "v_plan_vs_real_realkey_final"  # Real LOB no debe depender del plan


def view_exists(conn, schema: str, name: str) -> bool:
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM information_schema.views
        WHERE table_schema = %s AND table_name = %s
    """, (schema, name))
    out = cur.fetchone()
    cur.close()
    return out is not None


def table_exists(conn, schema: str, name: str) -> bool:
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
    """, (schema, name))
    out = cur.fetchone()
    cur.close()
    return out is not None


def view_definition(conn, schema: str, name: str) -> str:
    cur = conn.cursor()
    cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", (f"{schema}.{name}",))
    row = cur.fetchone()
    cur.close()
    return (row[0] or "").lower()


def main() -> int:
    errors = []
    warnings = []
    try:
        init_db_pool()
    except Exception as e:
        print(f"FAIL: DB init: {e}")
        return 1
    with get_db() as conn:
        for schema, name in REQUIRED_TABLES:
            if not table_exists(conn, schema, name):
                errors.append(f"Tabla {schema}.{name} no existe. Ejecutar migración 041.")
        for schema, name in REQUIRED_VIEWS:
            if not view_exists(conn, schema, name):
                errors.append(f"Vista {schema}.{name} no existe. Ejecutar migración 041.")
        if not errors:
            for schema, name in REQUIRED_VIEWS:
                try:
                    def_ = view_definition(conn, schema, name)
                    if FORBIDDEN_VIEW_DEPENDENCY in def_:
                        errors.append(f"Vista {schema}.{name} depende de {FORBIDDEN_VIEW_DEPENDENCY} (Real LOB no debe depender de Plan).")
                except Exception as e:
                    warnings.append(f"No se pudo inspeccionar definición de {schema}.{name}: {e}")
            for schema, name in [("ops", "v_real_trips_by_lob_month"), ("ops", "v_real_trips_by_lob_week")]:
                try:
                    cur = conn.cursor()
                    cur.execute(f"SELECT 1 FROM {schema}.{name} LIMIT 1")
                    if cur.fetchone() is None:
                        warnings.append(f"{schema}.{name} está vacía (puede ser esperado si no hay datos o mapping).")
                    cur.close()
                except Exception as e:
                    warnings.append(f"Sample {schema}.{name}: {e}")
    print("=== REAL LOB Observability contract check ===\n")
    if errors:
        print("Errors:")
        for e in errors:
            print("  -", e)
        print("\nResult: FAIL")
        return 1
    if warnings:
        print("Warnings:")
        for w in warnings:
            print("  -", w)
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
