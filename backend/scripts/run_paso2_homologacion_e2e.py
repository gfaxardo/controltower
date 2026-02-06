"""
YEGO CONTROL TOWER - Paso 2 E2E: Homologación LOB PLAN vs REAL.
Ejecuta precheck, reportes, inserción de matches exactos y gap reports.
No modifica lógica madre (LOB REAL = tipo_servicio, B2B = pago_corporativo).

En entornos con trips_all muy grande, las vistas pueden ser lentas.
Aumentar statement_timeout en el servidor o ejecutar: SET statement_timeout = '300s';
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def run_query(cursor, sql, description=""):
    try:
        cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print(f"  [ERROR] {description}: {e}")
        return None

def run_update(cursor, sql, description=""):
    try:
        cursor.execute(sql)
        return cursor.rowcount
    except Exception as e:
        print(f"  [ERROR] {description}: {e}")
        return -1

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '180000'")  # 180s para consultas pesadas
        except Exception:
            pass

        # ----- 0) PRECHECK -----
        print("=== 0) PRECHECK ===\n")

        # Vistas 2C+
        for view in ["ops.v_real_lob_base", "ops.v_real_lob_resolution", "ops.v_real_tipo_servicio_universe"]:
            schema, name = view.split(".")
            cur.execute("""
                SELECT 1 FROM information_schema.views 
                WHERE table_schema = %s AND table_name = %s
            """, (schema, name))
            exists = cur.fetchone()
            print(f"  {view}: {'OK' if exists else 'NO EXISTE'}")

        # trips_all: existencia y columna fecha (sin COUNT para evitar timeout en tablas grandes)
        cur.execute("""
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'trips_all'
        """)
        trips_all_exists = cur.fetchone() is not None
        print(f"  public.trips_all existe: {'Sí' if trips_all_exists else 'No'}")
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'trips_all' 
            AND column_name IN ('fecha_inicio_viaje', 'trip_date', 'tipo_servicio')
            ORDER BY ordinal_position
        """)
        date_cols = [r[0] for r in cur.fetchall()]
        print(f"  Columnas clave (fecha/tipo_servicio): {[c for c in date_cols]}")
        total_trips = "N/A (ejecutar COUNT con timeout alto si se necesita)"
        print(f"  Conteo 2025/2026: omitido en E2E (tabla grande); ejecutar a mano si aplica.\n")

        # ----- 1) REPORTE TOP 50 real_tipo_servicio -----
        total_real_lob = 0
        print("=== 1) UNIVERSO REAL - Top 50 real_tipo_servicio (global) ===\n")
        try:
            top_real = run_query(cur, """
                SELECT real_tipo_servicio, SUM(trips_count) AS trips
                FROM ops.v_real_tipo_servicio_universe
                GROUP BY real_tipo_servicio
                ORDER BY trips DESC
                LIMIT 50
            """, "top 50 real")
            if top_real:
                for r in top_real[:20]:
                    print(f"  {str(r[0]):<40} {r[1]:>12,}")
                if len(top_real) > 20:
                    print(f"  ... y {len(top_real)-20} más\n")
            top_real = top_real or []
            r2 = run_query(cur, "SELECT COUNT(DISTINCT real_tipo_servicio) FROM ops.v_real_tipo_servicio_universe", "count real")
            total_real_lob = r2[0][0] if r2 and r2[0] else 0
            print(f"  Total real_tipo_servicio distintos: {total_real_lob}\n")
        except Exception as e:
            print(f"  [TIMEOUT/ERROR] {e}\n  Total real_tipo_servicio: N/A\n")

        # ----- 2) STAGING: verificar tabla -----
        print("=== 2) STAGING ===\n")
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'staging' AND table_name = 'plan_projection_raw'
        """)
        staging_ok = cur.fetchone()[0] > 0
        print(f"  staging.plan_projection_raw: {'OK' if staging_ok else 'NO EXISTE'}")
        if staging_ok:
            cur.execute("SELECT COUNT(*), MIN(period_date), MAX(period_date) FROM staging.plan_projection_raw")
            r = cur.fetchone()
            print(f"  Filas en staging: {r[0]}, period_date: {r[1]} .. {r[2]}\n")

        # ----- 3) UNIVERSO PLAN -----
        print("=== 3) UNIVERSO PLAN (v_plan_lob_universe_raw) ===\n")
        try:
            cur.execute("""
                SELECT plan_lob_name, SUM(trips_plan) AS trips
                FROM ops.v_plan_lob_universe_raw
                GROUP BY plan_lob_name
                ORDER BY trips DESC
                LIMIT 50
            """)
            top_plan = cur.fetchall()
            for r in top_plan[:20]:
                print(f"  {str(r[0]):<40} {r[1]:>12,.0f}")
            cur.execute("SELECT COUNT(DISTINCT plan_lob_name) FROM ops.v_plan_lob_universe_raw")
            total_plan_lob = cur.fetchone()[0]
        except Exception as e:
            print(f"  (vista vacía o sin datos): {e}")
            total_plan_lob = 0
            top_plan = []
        print(f"  Total plan_lob_name distintos: {total_plan_lob}\n")

        # ----- 4) TABLA HOMOLOGACIÓN -----
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'ops' AND table_name = 'lob_homologation'")
        hom_ok = cur.fetchone()[0] > 0
        print("=== 4) ops.lob_homologation ===\n  " + ("OK" if hom_ok else "NO EXISTE") + "\n")

        # ----- 5) INSERCIÓN SOLO MATCHES EXACTOS -----
        inserted = 0
        print("=== 5) INSERCIÓN MATCHES EXACTOS (high) ===\n")
        try:
            before = run_query(cur, "SELECT COUNT(*) FROM ops.lob_homologation", "count hom") or [(0,)]
            before = before[0][0] if before else 0
            rc = run_update(cur, """
                INSERT INTO ops.lob_homologation (country, city, real_tipo_servicio, plan_lob_name, confidence, notes)
                SELECT s.country, s.city, s.real_tipo_servicio, s.plan_lob_name, 'high', 'auto exact match'
                FROM ops.v_lob_homologation_suggestions s
                WHERE s.suggested_confidence = 'high'
                ON CONFLICT (country, city, real_tipo_servicio, plan_lob_name) DO NOTHING
            """, "insert exact matches")
            conn.commit()
            if rc is None or rc < 0:
                try:
                    cur.execute("""
                        INSERT INTO ops.lob_homologation (country, city, real_tipo_servicio, plan_lob_name, confidence, notes)
                        SELECT country, city, r_original, p_original, 'high', 'auto exact match'
                        FROM ops.v_lob_homologation_suggestions WHERE suggested_confidence = 'high'
                        ON CONFLICT (country, city, real_tipo_servicio, plan_lob_name) DO NOTHING
                    """)
                    inserted = cur.rowcount
                    conn.commit()
                except Exception as e2:
                    print(f"  Insert alternativo: {e2}")
            else:
                inserted = rc
            after = run_query(cur, "SELECT COUNT(*) FROM ops.lob_homologation", "count hom after") or [(0,)]
            after = after[0][0] if after else before
            print(f"  Homologaciones antes: {before}, después: {after}, insertadas: {inserted}\n")
        except Exception as e:
            print(f"  [ERROR] {e}\n")

        # ----- 6) GAP REPORTS -----
        gap_real = []
        gap_plan = []
        print("=== 6) GAP REPORT - Real sin homologación (top 20) ===\n")
        try:
            gap_real = run_query(cur, """
                SELECT u.country, u.city, u.real_tipo_servicio, u.trips_count
                FROM ops.v_real_tipo_servicio_universe u
                LEFT JOIN ops.lob_homologation h
                  ON (h.country IS NULL OR h.country = u.country)
                 AND (h.city IS NULL OR h.city = u.city)
                 AND TRIM(LOWER(h.real_tipo_servicio)) = TRIM(LOWER(u.real_tipo_servicio))
                WHERE h.homologation_id IS NULL
                ORDER BY u.trips_count DESC
                LIMIT 20
            """, "gap real") or []
            for r in gap_real:
                print(f"  {str(r[0]):<12} {str(r[1]):<20} {str(r[2]):<35} {r[3]:>10,}")
        except Exception as e:
            print(f"  [ERROR] {e}\n")

        print("\n=== 6) GAP REPORT - Plan sin homologación (top 20) ===\n")
        try:
            gap_plan = run_query(cur, """
                SELECT p.country, p.city, p.plan_lob_name, p.trips_plan
                FROM ops.v_plan_lob_universe_raw p
                LEFT JOIN ops.lob_homologation h
                  ON (h.country IS NULL OR h.country = p.country)
                 AND (h.city IS NULL OR h.city = p.city)
                 AND TRIM(LOWER(h.plan_lob_name)) = TRIM(LOWER(p.plan_lob_name))
                WHERE h.homologation_id IS NULL
                ORDER BY p.trips_plan DESC
                LIMIT 20
            """, "gap plan") or []
            for r in gap_plan:
                print(f"  {str(r[0]):<12} {str(r[1]):<20} {str(r[2]):<35} {r[3]:>10,.0f}")
        except Exception as e:
            print(f"  {e}")

        # ----- 7) SUGERENCIAS LOW (próximos 10 manuales) -----
        suggestions = []
        print("\n=== 7) SUGERENCIAS LOW - Próximos 10 mappings por impacto ===\n")
        try:
            suggestions = run_query(cur, """
                SELECT country, city, real_tipo_servicio, plan_lob_name, suggested_confidence, real_trips_count, plan_trips
                FROM ops.v_lob_homologation_suggestions
                WHERE suggested_confidence = 'low'
                ORDER BY COALESCE(real_trips_count, 0) DESC, COALESCE(plan_trips, 0) DESC
                LIMIT 10
            """, "suggestions low") or []
            for s in suggestions:
                print(f"  real={s[2]} -> plan={s[3]} (conf={s[4]}) trips_real={(s[5] or 0):,.0f} plan={(s[6] or 0):,.0f}")
        except Exception as e:
            print(f"  {e}")

        cur.close()

    # ----- 8) RESUMEN EJECUTIVO -----
    print("\n" + "="*60)
    print("RESUMEN EJECUTIVO - PASO 2 HOMOLOGACIÓN LOB")
    print("="*60)
    print(f"  - Total real_tipo_servicio distintos: {total_real_lob}")
    print(f"  - Total plan_lob_name distintos: {total_plan_lob}")
    print(f"  - Homologaciones high creadas (esta ejecución): {inserted}")
    print(f"  - Top 20 gaps REAL mostrados arriba")
    print(f"  - Top 20 gaps PLAN mostrados arriba")
    print(f"  - Próximos 10 mappings manuales sugeridos (suggestions low) listados arriba")
    print("="*60)

if __name__ == "__main__":
    main()
