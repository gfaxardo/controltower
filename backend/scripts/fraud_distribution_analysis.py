"""Fase 1F-5B — Distribution Analysis.

Calcula distribuciones reales de metrica de viajes para calibracion de thresholds.
Usa SQL agregada (no trae filas a Python).
"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db

SOURCE = "public.trips_2026"

def percentile_query(metric_expr, source_table, where_clause="", limit=None):
    """Build percentile SQL."""
    q = f"""
        SELECT
            COUNT(*) AS n,
            MIN({metric_expr}) AS min_val,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY {metric_expr}) AS p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {metric_expr}) AS p75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY {metric_expr}) AS p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {metric_expr}) AS p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY {metric_expr}) AS p99,
            MAX({metric_expr}) AS max_val,
            AVG({metric_expr}) AS avg_val,
            STDDEV({metric_expr}) AS stddev_val
        FROM {source_table}
        WHERE {where_clause if where_clause else '1=1'}
    """
    return q

def format_dist(n, p50, p75, p90, p95, p99, maxv, avg, stddev):
    return {
        "n": int(n or 0),
        "p50": round(float(p50 or 0), 2),
        "p75": round(float(p75 or 0), 2),
        "p90": round(float(p90 or 0), 2),
        "p95": round(float(p95 or 0), 2),
        "p99": round(float(p99 or 0), 2),
        "max": round(float(maxv or 0), 2),
        "avg": round(float(avg or 0), 2),
        "stddev": round(float(stddev or 0), 2),
    }

def main():
    window_days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    
    print(f"=== FASE 1F-5B DISTRIBUTION ANALYSIS === D-{window_days}")
    t0 = datetime.now()
    
    results = {"window_days": window_days, "computed_at": datetime.now().isoformat()}
    
    with get_db() as conn:
        cur = conn.cursor()
        
        # ── 1. Trips per driver ──
        print("\n1. Trips per driver (D-" + str(window_days) + ")")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY cnt) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY cnt) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY cnt) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY cnt) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY cnt) AS p99,
                MAX(cnt) AS maxv,
                AVG(cnt) AS avgv,
                STDDEV(cnt) AS stdv
            FROM (
                SELECT conductor_id, COUNT(*) AS cnt
                FROM {SOURCE}
                WHERE condicion = 'Completado'
                  AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                GROUP BY conductor_id
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["trips_per_driver"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']} p95={dist['p95']} p99={dist['p99']} max={dist['max']}")

        # ── 2. Unique origins per driver ──
        print("\n2. Unique origins per driver")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY cnt) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY cnt) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY cnt) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY cnt) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY cnt) AS p99,
                MAX(cnt) AS maxv, AVG(cnt) AS avgv, STDDEV(cnt) AS stdv
            FROM (
                SELECT conductor_id,
                       COUNT(DISTINCT SPLIT_PART(direccion, '->', 1)) AS cnt
                FROM {SOURCE}
                WHERE condicion = 'Completado'
                  AND direccion LIKE '%%->%%'
                  AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                GROUP BY conductor_id
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["unique_origins_per_driver"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p90={dist['p90']} p95={dist['p95']}")

        # ── 3. Repeated origin count (max trips from same origin) ──
        print("\n3. Max repeated origin per driver")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY max_cnt) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY max_cnt) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY max_cnt) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY max_cnt) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY max_cnt) AS p99,
                MAX(max_cnt) AS maxv, AVG(max_cnt) AS avgv, STDDEV(max_cnt) AS stdv
            FROM (
                SELECT driver_id, MAX(trip_count) AS max_cnt
                FROM (
                    SELECT conductor_id AS driver_id,
                           SPLIT_PART(direccion, '->', 1) AS origin_raw,
                           COUNT(*) AS trip_count
                    FROM {SOURCE}
                    WHERE condicion = 'Completado'
                      AND direccion LIKE '%%->%%'
                      AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                    GROUP BY conductor_id, SPLIT_PART(direccion, '->', 1)
                ) sub2
                GROUP BY driver_id
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["max_repeated_origin"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']} p95={dist['p95']} p99={dist['p99']}")

        # ── 4. Repeated route count ──
        print("\n4. Max repeated route per driver")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY max_cnt) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY max_cnt) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY max_cnt) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY max_cnt) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY max_cnt) AS p99,
                MAX(max_cnt) AS maxv, AVG(max_cnt) AS avgv, STDDEV(max_cnt) AS stdv
            FROM (
                SELECT driver_id, MAX(trip_count) AS max_cnt
                FROM (
                    SELECT conductor_id AS driver_id,
                           LOWER(direccion) AS route_sig,
                           COUNT(*) AS trip_count
                    FROM {SOURCE}
                    WHERE condicion = 'Completado'
                      AND direccion LIKE '%%->%%'
                      AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                    GROUP BY conductor_id, LOWER(direccion)
                ) sub2
                GROUP BY driver_id
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["max_repeated_route"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p90={dist['p90']} p95={dist['p95']} p99={dist['p99']}")

        # ── 5. Avg distance per driver ──
        print("\n5. Avg distance (km) per driver")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY avgd) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY avgd) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY avgd) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avgd) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY avgd) AS p99,
                MAX(avgd) AS maxv, AVG(avgd) AS avgv, STDDEV(avgd) AS stdv
            FROM (
                SELECT conductor_id, AVG(COALESCE(distancia_km, 0)) AS avgd
                FROM {SOURCE}
                WHERE condicion = 'Completado'
                  AND distancia_km IS NOT NULL
                  AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                GROUP BY conductor_id
                HAVING COUNT(*) >= 3
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["avg_distance_km"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']} p10 (avg)={dist['avg']}")

        # ── 6. Avg duration per driver (seconds) ──
        print("\n6. Avg duration (s) per driver")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY avgd) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY avgd) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY avgd) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avgd) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY avgd) AS p99,
                MAX(avgd) AS maxv, AVG(avgd) AS avgv, STDDEV(avgd) AS stdv
            FROM (
                SELECT conductor_id, AVG(EXTRACT(EPOCH FROM (fecha_finalizacion - fecha_inicio_viaje))) AS avgd
                FROM {SOURCE}
                WHERE condicion = 'Completado'
                  AND fecha_finalizacion IS NOT NULL
                  AND fecha_inicio_viaje IS NOT NULL
                  AND fecha_finalizacion > fecha_inicio_viaje
                  AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                GROUP BY conductor_id
                HAVING COUNT(*) >= 3
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["avg_duration_s"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']}")

        # ── 7. Short trip ratio per driver ──
        print("\n7. Short trip ratio per driver (dist<2km or dur<3min)")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ratio) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY ratio) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY ratio) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ratio) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY ratio) AS p99,
                MAX(ratio) AS maxv, AVG(ratio) AS avgv, STDDEV(ratio) AS stdv
            FROM (
                SELECT conductor_id,
                       COUNT(*) FILTER (WHERE COALESCE(distancia_km,0)*1000 < 2000
                                         OR EXTRACT(EPOCH FROM (fecha_finalizacion-fecha_inicio_viaje)) < 180)::float
                       / NULLIF(COUNT(*), 0) AS ratio
                FROM {SOURCE}
                WHERE condicion = 'Completado'
                  AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                GROUP BY conductor_id
                HAVING COUNT(*) >= 3
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["short_trip_ratio"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']} p95={dist['p95']}")

        # ── 8. Variance distance per driver ──
        print("\n8. Variance distance per driver")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY vd) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY vd) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY vd) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY vd) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY vd) AS p99,
                MAX(vd) AS maxv, AVG(vd) AS avgv, STDDEV(vd) AS stdv
            FROM (
                SELECT conductor_id, VARIANCE(COALESCE(distancia_km,0)*1000) AS vd
                FROM {SOURCE}
                WHERE condicion = 'Completado'
                  AND distancia_km IS NOT NULL
                  AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                GROUP BY conductor_id
                HAVING COUNT(*) >= 5
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["variance_distance_m2"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']}")

        # ── 9. Drivers per origin cluster ──
        print("\n9. Drivers per origin cluster")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY dc) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY dc) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY dc) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY dc) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY dc) AS p99,
                MAX(dc) AS maxv, AVG(dc) AS avgv, STDDEV(dc) AS stdv
            FROM (
                SELECT SPLIT_PART(direccion, '->', 1) AS origin,
                       COUNT(DISTINCT conductor_id) AS dc
                FROM {SOURCE}
                WHERE condicion = 'Completado'
                  AND direccion LIKE '%%->%%'
                  AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                GROUP BY SPLIT_PART(direccion, '->', 1)
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["drivers_per_origin"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']} p95={dist['p95']} p99={dist['p99']} max={dist['max']}")

        # ── 10. Card amount distribution (new drivers) ──
        print("\n10. Card amount distribution (drivers with completed trips)")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY precio_yango_pro) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY precio_yango_pro) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY precio_yango_pro) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY precio_yango_pro) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY precio_yango_pro) AS p99,
                MAX(precio_yango_pro) AS maxv,
                AVG(precio_yango_pro) AS avgv,
                STDDEV(precio_yango_pro) AS stdv
            FROM {SOURCE}
            WHERE condicion = 'Completado'
              AND tarjeta > 0
              AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["card_amount"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']} p95={dist['p95']} p99={dist['p99']}")

        # ── 11. Burst activity (trips per driver 24h) ──
        print("\n11. Max trips 24h per driver")
        cur.execute(f"""
            SELECT
                COUNT(*) AS n,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY max24h) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY max24h) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY max24h) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY max24h) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY max24h) AS p99,
                MAX(max24h) AS maxv, AVG(max24h) AS avgv, STDDEV(max24h) AS stdv
            FROM (
                SELECT conductor_id, MAX(cnt) AS max24h
                FROM (
                    SELECT conductor_id, DATE(fecha_inicio_viaje) AS d, COUNT(*) AS cnt
                    FROM {SOURCE}
                    WHERE condicion = 'Completado'
                      AND fecha_inicio_viaje >= NOW() - INTERVAL '{window_days} days'
                    GROUP BY conductor_id, DATE(fecha_inicio_viaje)
                ) sub2
                GROUP BY conductor_id
            ) sub
        """)
        r = cur.fetchone()
        dist = format_dist(*r)
        results["max_trips_24h"] = dist
        print(f"  n={dist['n']} p50={dist['p50']} p75={dist['p75']} p90={dist['p90']} p95={dist['p95']} p99={dist['p99']} max={dist['max']}")

        cur.close()

    elapsed = (datetime.now() - t0).total_seconds()
    results["elapsed_seconds"] = elapsed
    
    # Write report
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "fraud",
        "AUDITORIA_FASE1F5B_DISTRIBUTIONS.md",
    )
    
    md = []
    md.append("# AUDITORIA FASE 1F-5B — DISTRIBUCIONES REALES")
    md.append(f"\n**Fecha**: {results['computed_at']}")
    md.append(f"\n**Ventana**: D-{window_days}")
    md.append(f"\n**Elapsed**: {elapsed:.1f}s")
    
    for metric, d in results.items():
        if isinstance(d, dict) and 'p50' in d:
            md.append(f"\n## {metric}")
            md.append(f"\n| Percentil | Valor |")
            md.append(f"\n|---|---|")
            md.append(f"\n| n | {d['n']} |")
            md.append(f"\n| p50 | {d['p50']} |")
            md.append(f"\n| p75 | {d['p75']} |")
            md.append(f"\n| p90 | {d['p90']} |")
            md.append(f"\n| p95 | {d['p95']} |")
            md.append(f"\n| p99 | {d['p99']} |")
            md.append(f"\n| max | {d['max']} |")
            md.append(f"\n| avg | {d['avg']} |")
            md.append(f"\n| stddev | {d['stddev']} |")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    
    print(f"\nReport saved: {output_path}")
    print(f"Elapsed: {elapsed:.1f}s")
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
