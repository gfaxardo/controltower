#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
QA Script - Fase 0.1: Projection Ownership Governance.
"""
import os, sys, io, csv, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from app.services.control_loop_projection_parser import parse_control_loop_csv
from app.adapters.projection_ownership_repo import sync_ownership_from_staging, get_ownership_summary

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)
W = 68
_results = {}
CSV_PATH = r"c:\Users\Pc\Downloads\plantilla proyeccion Control Tower - DRIVERS.csv"

def _hdr(t): print(); print("-" * W); print(f"  {t}"); print("-" * W)
def _check(label, ok, detail=""):
    _results[label] = ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {'OK' if ok else 'XX'} {label}")
    if detail: print(f"         {detail}")
    return ok

def check_table_exists():
    _hdr("CHECK 1: Tabla ops.projection_ownership existe")
    try:
        init_db_pool()
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='projection_ownership')")
            ok = cur.fetchone()[0]; cur.close()
        _check("Tabla ops.projection_ownership", ok)
        if ok:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ops' AND table_name='projection_ownership' ORDER BY ordinal_position")
                cols = [r[0] for r in cur.fetchall()]; cur.close()
            print(f"         Columnas: {cols}")
            for c in ("plan_version_key","linea_negocio_canonica","jefe_producto","estado"):
                _check(f"  Columna '{c}'", c in cols)
    except Exception as e:
        _check("Conexion", False, str(e))

def check_unique_constraint():
    _hdr("CHECK 2: UNIQUE index/constraint activo")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname='ops' AND tablename='projection_ownership' AND indexdef ILIKE '%UNIQUE%'")
            cs = [r[0] for r in cur.fetchall()]; cur.close()
        _check("UNIQUE index existe", len(cs)>0, str(cs))
    except Exception as e:
        _check("Constraint check", False, str(e))

def check_staging_has_ownership_data():
    _hdr("CHECK 3: staging tiene columnas ownership")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='staging' AND table_name='control_loop_plan_metric_long' AND column_name IN ('jefe_producto','producto','estado') ORDER BY column_name")
            cols = {r[0] for r in cur.fetchall()}; cur.close()
        for c in ("estado","jefe_producto","producto"):
            _check(f"staging tiene '{c}'", c in cols)
    except Exception as e:
        _check("Staging columns", False, str(e))

def check_new_csv_parse():
    _hdr("CHECK 4: CSV nuevo parsea ownership")
    if not os.path.exists(CSV_PATH):
        _check("CSV encontrado", False, CSV_PATH); return
    try:
        with open(CSV_PATH,"rb") as f: content = f.read()
        rows, months = parse_control_loop_csv(content, "DRIVERS.csv")
        _check(f"Rows: {len(rows)}", len(rows)>0)
        s = rows[0]
        _check("jefe_producto en output", "jefe_producto" in s, str(s.get("jefe_producto")))
        _check("estado en output", "estado" in s, str(s.get("estado")))
        jefes = set(r.get("jefe_producto") for r in rows if r.get("jefe_producto"))
        _check(f"Jefes: {jefes}", len(jefes)==3)
        for j in ("Ariana","Eduardo","Stacy"): _check(j, j in jefes)
    except Exception as e:
        _check("CSV parse", False, str(e))

def check_legacy_csv_still_works():
    _hdr("CHECK 5: Legacy CSV funciona")
    try:
        c = io.BytesIO(b"country,city,linea_negocio,metric,2026-01,2026-02\r\nPE,Lima,Auto regular,active_drivers,100,200\r\n").read()
        rows, _ = parse_control_loop_csv(c, "test.csv")
        _check(f"Legacy rows: {len(rows)}", len(rows)==2)
        _check("jefe_producto ausente", rows[0].get("jefe_producto") is None)
    except Exception as e:
        _check("Legacy parse", False, str(e))

def check_sync_deduplication():
    _hdr("CHECK 6: Sync deduplica metricas -> 1 row por LOB")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT plan_version FROM staging.control_loop_plan_metric_long WHERE jefe_producto IS NOT NULL ORDER BY created_at DESC LIMIT 1")
            r = cur.fetchone(); cur.close()
        if not r: _check("Datos ownership en staging", False, "No hay plan_version con ownership"); return
        pv = r[0]
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM staging.control_loop_plan_metric_long WHERE plan_version=%s AND jefe_producto IS NOT NULL",(pv,))
            sc = cur.fetchone()[0]; cur.close()
        _check(f"Filas staging con ownership: {sc}", sc>0)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(DISTINCT (country, city, linea_negocio_canonica)) FROM staging.control_loop_plan_metric_long WHERE plan_version=%s AND jefe_producto IS NOT NULL",(pv,))
            uc = cur.fetchone()[0]; cur.close()
        _check(f"Combos unicos: {uc}", uc>0)
        _check(f"Dedup: staging={sc} > combos={uc}", uc<sc, "OK, staging tiene mas filas que combos dimensionales")
    except Exception as e:
        _check("Sync dedup", False, str(e))

def check_ownership_summary_endpoint():
    _hdr("CHECK 7: get_ownership_summary() funciona")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT plan_version_key FROM ops.projection_ownership ORDER BY created_at DESC LIMIT 1")
            r = cur.fetchone(); cur.close()
        if not r: _check("Datos en ownership", False, "No hay datos"); return
        pv = r[0]; s = get_ownership_summary(pv)
        _check(f"total_ownership_rows: {s.get('total_ownership_rows')}", s.get("total_ownership_rows",0)>0)
        _check(f"owners_detected: {s.get('owners_detected')}", len(s.get("owners_detected") or [])>0)
        _check("conflicts_count", "conflicts_count" in s)
        _check("missing_owner_count", "missing_owner_count" in s)
        _check("rows_by_owner", isinstance(s.get("rows_by_owner"), dict))
    except Exception as e:
        _check("Summary", False, str(e))

def check_canonical_untouched():
    _hdr("CHECK 8: ops.plan_trips_monthly sin columnas ownership")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ops' AND table_name='plan_trips_monthly' AND column_name IN ('jefe_producto','producto','estado')")
            found = {r[0] for r in cur.fetchall()}; cur.close()
        for c in ("jefe_producto","producto","estado"):
            _check(f"'{c}' NO en plan_trips_monthly", c not in found)
    except Exception as e:
        _check("Canonical check", False, str(e))

def check_omniview_responsive():
    _hdr("CHECK 9: Omniview responde")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM ops.v_plan_projection_control_loop")
            n = cur.fetchone()[0]; cur.close()
        _check(f"v_plan_projection_control_loop rows: {n}", n>=0)
    except Exception as e:
        _check("Omniview", False, str(e))

def main():
    print()
    print("=" * W)
    print("  QA - Fase 0.1: Projection Ownership Governance")
    print("=" * W)
    checks = [
        ("Tabla ops.projection_ownership", check_table_exists),
        ("UNIQUE constraint", check_unique_constraint),
        ("Staging columns ownership", check_staging_has_ownership_data),
        ("CSV nuevo parsea ownership", check_new_csv_parse),
        ("Legacy CSV funciona", check_legacy_csv_still_works),
        ("Sync deduplication", check_sync_deduplication),
        ("get_ownership_summary()", check_ownership_summary_endpoint),
        ("Canonical untouched", check_canonical_untouched),
        ("Omniview responsive", check_omniview_responsive),
    ]
    for name, fn in checks:
        try: fn()
        except Exception as e: _check(name, False, str(e))
    _hdr("RESUMEN FINAL")
    p = sum(1 for v in _results.values() if v); t = len(_results)
    print(f"  PASS: {p}/{t}")
    if p==t: print("\n  >>> GO: Fase 0.1 lista para produccion.")
    elif p>=t-1: print("\n  >>> CONDITIONAL GO: revisar el fallo.")
    else: print("\n  >>> NO-GO: corregir fallos antes de avanzar.")
    print()

if __name__ == "__main__":
    main()
