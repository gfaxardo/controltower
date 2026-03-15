#!/usr/bin/env python3
"""
FASE A — CT-REAL-LOB-FINAL-CLOSURE.
Audita en BD si los artefactos de la migración 098 existen y son correctos.
No modifica nada; solo consultas de lectura.

Salida: objetos_098_existentes, objetos_098_faltantes, 098_aplicada_realmente (yes/no),
y si las MVs dependen de la capa _120d.
Uso: cd backend && python scripts/audit_098_artifacts.py
"""
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass


def main():
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        existentes = []
        faltantes = []

        # --- A. Índices ---
        cur.execute("""
            SELECT schemaname, tablename, indexname
            FROM pg_indexes
            WHERE indexname IN ('ix_trips_all_fecha_inicio_viaje', 'ix_trips_2026_fecha_inicio_viaje')
        """)
        idx_found = {row[2] for row in cur.fetchall()}
        for name in ('ix_trips_all_fecha_inicio_viaje', 'ix_trips_2026_fecha_inicio_viaje'):
            if name in idx_found:
                existentes.append(("index", name))
            else:
                faltantes.append(("index", name))

        # --- B. Vistas ---
        cur.execute("""
            SELECT schemaname, viewname
            FROM pg_views
            WHERE schemaname = 'ops' AND viewname IN (
                'v_trips_real_canon_120d',
                'v_real_trips_service_lob_resolved_120d',
                'v_real_trips_with_lob_v2_120d'
            )
        """)
        views_found = {row[1] for row in cur.fetchall()}
        for name in ('v_trips_real_canon_120d', 'v_real_trips_service_lob_resolved_120d', 'v_real_trips_with_lob_v2_120d'):
            if name in views_found:
                existentes.append(("view", "ops." + name))
            else:
                faltantes.append(("view", "ops." + name))

        # --- C. MVs ---
        cur.execute("""
            SELECT schemaname, matviewname
            FROM pg_matviews
            WHERE schemaname = 'ops' AND matviewname IN ('mv_real_lob_month_v2', 'mv_real_lob_week_v2')
        """)
        mvs_found = {row[1] for row in cur.fetchall()}
        for name in ('mv_real_lob_month_v2', 'mv_real_lob_week_v2'):
            if name in mvs_found:
                existentes.append(("materialized_view", "ops." + name))
            else:
                faltantes.append(("materialized_view", "ops." + name))

        # --- D. Definición MVs: que usen v_real_trips_with_lob_v2_120d ---
        mvs_use_120d = {}
        for mv in ('mv_real_lob_month_v2', 'mv_real_lob_week_v2'):
            if mv not in mvs_found:
                mvs_use_120d[mv] = None
                continue
            cur.execute("""
                SELECT pg_get_viewdef(%s::regclass, true)
            """, ("ops." + mv,))
            row = cur.fetchone()
            defn = (row[0] or "").lower() if row else ""
            mvs_use_120d[mv] = "v_real_trips_with_lob_v2_120d" in defn

        # --- Alembic current ---
        cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
        alembic_row = cur.fetchone()
        alembic_current = alembic_row[0] if alembic_row else None

        # --- Conteos MVs (si no están pobladas, no se puede COUNT) ---
        month_rows = week_rows = None
        if 'mv_real_lob_month_v2' in mvs_found:
            try:
                cur.execute("SELECT COUNT(*) FROM ops.mv_real_lob_month_v2")
                month_rows = cur.fetchone()[0]
            except Exception:
                conn.rollback()
                month_rows = "not_populated"
        if 'mv_real_lob_week_v2' in mvs_found:
            try:
                cur.execute("SELECT COUNT(*) FROM ops.mv_real_lob_week_v2")
                week_rows = cur.fetchone()[0]
            except Exception:
                conn.rollback()
                week_rows = "not_populated"
    # end with

    all_required = (
        len([x for x in existentes if x[0] == "index"]) == 2 and
        len([x for x in existentes if x[0] == "view"]) == 3 and
        len([x for x in existentes if x[0] == "materialized_view"]) == 2
    )
    mvs_correct_def = all(mvs_use_120d.get(mv) is True for mv in ('mv_real_lob_month_v2', 'mv_real_lob_week_v2') if mvs_use_120d.get(mv) is not None)
    aplicada_realmente = "yes" if (all_required and mvs_correct_def) else "no"

    out = {
        "objetos_098_existentes": existentes,
        "objetos_098_faltantes": faltantes,
        "098_aplicada_realmente": aplicada_realmente,
        "mvs_usando_capa_120d": mvs_use_120d,
        "alembic_version_actual": alembic_current,
        "mv_real_lob_month_v2_rows": month_rows,
        "mv_real_lob_week_v2_rows": week_rows,
    }
    print(json.dumps(out, indent=2))
    return 0 if aplicada_realmente == "yes" else 1


if __name__ == "__main__":
    sys.exit(main())
