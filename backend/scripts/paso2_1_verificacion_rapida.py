"""
[YEGO CT] PASO 2.1 — Verificación rápida (sin timeouts) de homologación.
Ejecuta consultas con LIMIT. La decisión (avanzar o no) se basa en 1) y 2).
Las consultas de la sección 5 (universo real) pueden dar timeout si trips_all
es muy grande; en ese caso igual se muestra la salida correcta.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def run(cur, conn, sql, desc=""):
    try:
        cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        print(f"  [ERROR] {desc}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return None

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()

        # --- 1) STAGING ---
        print("=== 1) CARGA CSV (staging) ===\n")
        r = run(cur, conn, "SELECT COUNT(*) AS c FROM staging.plan_projection_raw", "count staging")
        rows_staging = r[0][0] if r else 0
        print(f"  rows_staging: {rows_staging}")

        r = run(cur, conn, "SELECT MIN(period_date), MAX(period_date) FROM staging.plan_projection_raw", "minmax")
        if r and r[0][0] is not None:
            print(f"  period_date: {r[0][0]} .. {r[0][1]}")
        else:
            print("  period_date: (vacío o NULL)")

        r = run(cur, conn, """
            SELECT country, city, COUNT(*) AS cnt
            FROM staging.plan_projection_raw
            GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20
        """, "top country city")
        if r:
            for row in r:
                print(f"    {str(row[0]):<15} {str(row[1]):<20} {row[2]:>8}")

        # --- 2) UNIVERSO PLAN ---
        print("\n=== 2) UNIVERSO PLAN ===\n")
        r = run(cur, conn, "SELECT COUNT(*) FROM ops.v_plan_lob_universe_raw", "count plan lobs")
        plan_lobs = r[0][0] if r else 0
        print(f"  plan_lobs: {plan_lobs}")

        r = run(cur, conn, """
            SELECT * FROM ops.v_plan_lob_universe_raw
            ORDER BY trips_plan DESC NULLS LAST LIMIT 30
        """, "top 30 plan")
        if r:
            for row in r[:15]:
                print(f"    {row}")
            if len(r) > 15:
                print(f"    ... y {len(r)-15} más")

        # --- 3) HOMOLOGACIONES (antes de consultas pesadas sobre real) ---
        print("\n=== 3) HOMOLOGACIONES EXACTAS ===\n")
        r = run(cur, conn, "SELECT COUNT(*) FROM ops.lob_homologation", "total hom")
        hom_total = r[0][0] if r else 0
        r = run(cur, conn, "SELECT COUNT(*) FROM ops.lob_homologation WHERE confidence='high'", "high hom")
        hom_high = r[0][0] if r else 0
        print(f"  homologations_total: {hom_total}")
        print(f"  homologations_high: {hom_high}")

        r = run(cur, conn, "SELECT * FROM ops.lob_homologation ORDER BY created_at DESC LIMIT 50", "last 50 hom")
        if r:
            for row in r[:10]:
                print(f"    {row}")
            if len(r) > 10:
                print(f"    ... y {len(r)-10} más")

        # --- 4) GAPS PLAN (sin usar vista real, rápido) ---
        print("\n=== 4) GAPS - Plan sin homologación (top 30) ===\n")
        r = run(cur, conn, """
            SELECT p.country,p.city,p.plan_lob_name,p.trips_plan
            FROM ops.v_plan_lob_universe_raw p
            LEFT JOIN ops.lob_homologation h
              ON (h.country IS NULL OR h.country=p.country)
             AND (h.city IS NULL OR h.city=p.city)
             AND lower(trim(h.plan_lob_name))=lower(trim(p.plan_lob_name))
            WHERE h.homologation_id IS NULL
            ORDER BY p.trips_plan DESC NULLS LAST
            LIMIT 30
        """, "gap plan")
        if r:
            for row in r:
                print(f"    {str(row[0]):<12} {str(row[1]):<20} {str(row[2]):<30} {row[3]:>10,.0f}")
        else:
            print("  (sin datos)")

        # --- 5) UNIVERSO REAL y GAP REAL (pueden dar timeout si trips_all es muy grande) ---
        print("\n=== 5) UNIVERSO REAL (top 30, puede ser lento) ===\n")
        r = run(cur, conn, "SELECT COUNT(DISTINCT real_tipo_servicio) FROM ops.v_real_tipo_servicio_universe", "count real")
        real_distinct = r[0][0] if r else "N/A"
        print(f"  COUNT(DISTINCT real_tipo_servicio): {real_distinct}")

        r = run(cur, conn, """
            SELECT * FROM ops.v_real_tipo_servicio_universe
            ORDER BY trips_count DESC LIMIT 30
        """, "top 30 real")
        if r:
            for row in r[:15]:
                print(f"    {row}")
            if len(r) > 15:
                print(f"    ... y {len(r)-15} más")
        else:
            print("  (sin datos o timeout)")

        print("\n=== 5) GAPS - Real sin homologación (top 30) ===\n")
        r = run(cur, conn, """
            SELECT u.country,u.city,u.real_tipo_servicio,u.trips_count
            FROM ops.v_real_tipo_servicio_universe u
            LEFT JOIN ops.lob_homologation h
              ON (h.country IS NULL OR h.country=u.country)
             AND (h.city IS NULL OR h.city=u.city)
             AND lower(trim(h.real_tipo_servicio))=lower(trim(u.real_tipo_servicio))
            WHERE h.homologation_id IS NULL
            ORDER BY u.trips_count DESC
            LIMIT 30
        """, "gap real")
        if r:
            for row in r:
                print(f"    {str(row[0]):<12} {str(row[1]):<20} {str(row[2]):<30} {row[3]:>10,}")
        else:
            print("  (sin datos o timeout)")

        cur.close()

    # --- SALIDA ---
    print("\n" + "="*60)
    if rows_staging == 0:
        print("  rows_staging = 0 => NO AVANZAR.")
        print("  Acción: cargar CSV con load_plan_projection_csv.py")
    elif plan_lobs > 0:
        print("  plan_lobs > 0 => AVANZAR A PASO 3.")
    else:
        print("  staging tiene filas pero plan_lobs = 0 (revisar vista/agrupación).")
    print("="*60)

if __name__ == "__main__":
    main()
