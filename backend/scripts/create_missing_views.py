#!/usr/bin/env python3
"""Crear vistas faltantes manualmente"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings
from app.db.connection import get_db, init_db_pool

def main():
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verificar si existe
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.views 
                WHERE table_schema='ops' AND table_name='v_plan_vs_real_monthly_latest'
            )
        """)
        exists = cursor.fetchone()[0]
        
        if exists:
            print("[OK] Vista ya existe")
            return
        
        print("[INFO] Creando vistas faltantes...")
        
        # Ejecutar SQL de la migración 007 directamente
        sql_statements = [
            # 1. Vista alias de mv_real_trips_monthly
            """
            DROP VIEW IF EXISTS ops.v_real_trips_monthly_latest CASCADE;
            CREATE VIEW ops.v_real_trips_monthly_latest AS
            SELECT 
                month,
                country,
                city,
                city_norm,
                park_id,
                lob_base,
                segment,
                trips_real_completed,
                active_drivers_real,
                avg_ticket_real,
                revenue_real_proxy,
                refreshed_at
            FROM ops.mv_real_trips_monthly
            ORDER BY month DESC, country, city_norm, lob_base, segment
            """,
            
            # 2. Vista de KPIs reales
            """
            DROP VIEW IF EXISTS ops.v_real_kpis_monthly CASCADE;
            CREATE VIEW ops.v_real_kpis_monthly AS
            SELECT 
                month,
                country,
                city,
                city_norm,
                park_id,
                lob_base,
                segment,
                trips_real_completed,
                active_drivers_real,
                avg_ticket_real,
                revenue_real_proxy,
                CASE 
                    WHEN active_drivers_real > 0 
                    THEN trips_real_completed::NUMERIC / active_drivers_real
                    ELSE NULL
                END AS trips_per_driver_real,
                refreshed_at
            FROM ops.mv_real_trips_monthly
            ORDER BY month DESC, country, city_norm, lob_base, segment
            """,
            
            # 3. Vista comparativa (la principal)
            """
            DROP VIEW IF EXISTS ops.v_plan_vs_real_monthly_latest CASCADE;
            CREATE VIEW ops.v_plan_vs_real_monthly_latest AS
            WITH latest_version AS (
                SELECT plan_version
                FROM ops.plan_trips_monthly
                GROUP BY plan_version
                ORDER BY MAX(created_at) DESC
                LIMIT 1
            ),
            plan_latest AS (
                SELECT 
                    p.plan_version,
                    p.country,
                    p.month,
                    COALESCE(p.plan_city_resolved_norm, p.city_norm) as city_norm_plan_effective,
                    p.lob_base,
                    p.segment,
                    p.projected_trips,
                    p.projected_drivers,
                    p.projected_ticket,
                    p.projected_trips_per_driver,
                    p.projected_revenue
                FROM ops.plan_trips_monthly p
                INNER JOIN latest_version lv ON p.plan_version = lv.plan_version
            ),
            real_aggregated AS (
                SELECT 
                    r.country,
                    r.month,
                    r.city_norm,
                    r.lob_base,
                    r.segment,
                    SUM(r.trips_real_completed) as trips_real_completed,
                    SUM(r.active_drivers_real) as active_drivers_real,
                    AVG(r.avg_ticket_real) FILTER (WHERE r.avg_ticket_real IS NOT NULL) as avg_ticket_real,
                    SUM(r.revenue_real_proxy) as revenue_real_proxy,
                    CASE 
                        WHEN SUM(r.active_drivers_real) > 0 
                        THEN SUM(r.trips_real_completed)::NUMERIC / SUM(r.active_drivers_real)
                        ELSE NULL
                    END AS trips_per_driver_real
                FROM ops.mv_real_trips_monthly r
                GROUP BY r.country, r.month, r.city_norm, r.lob_base, r.segment
            )
            SELECT 
                COALESCE(p.country, r.country) as country,
                COALESCE(p.month, r.month) as month,
                COALESCE(p.city_norm_plan_effective, r.city_norm) as city_norm_real,
                COALESCE(p.lob_base, r.lob_base) as lob_base,
                COALESCE(p.segment, r.segment) as segment,
                -- PLAN side
                p.plan_version,
                p.projected_trips,
                p.projected_drivers,
                p.projected_ticket,
                p.projected_trips_per_driver,
                p.projected_revenue,
                -- REAL side
                r.trips_real_completed,
                r.active_drivers_real,
                r.avg_ticket_real,
                r.trips_per_driver_real,
                r.revenue_real_proxy,
                -- GAPS (diferencias)
                (p.projected_trips - r.trips_real_completed) as gap_trips,
                (p.projected_drivers - r.active_drivers_real) as gap_drivers,
                (p.projected_ticket - r.avg_ticket_real) as gap_ticket,
                (p.projected_trips_per_driver - r.trips_per_driver_real) as gap_tpd,
                (p.projected_revenue - r.revenue_real_proxy) as gap_revenue_proxy,
                -- FLAGS
                CASE WHEN p.plan_version IS NOT NULL THEN TRUE ELSE FALSE END as has_plan,
                CASE WHEN r.trips_real_completed IS NOT NULL THEN TRUE ELSE FALSE END as has_real,
                CASE
                    WHEN p.plan_version IS NOT NULL AND r.trips_real_completed IS NOT NULL THEN 'matched'
                    WHEN p.plan_version IS NOT NULL AND r.trips_real_completed IS NULL THEN 'plan_only'
                    WHEN p.plan_version IS NULL AND r.trips_real_completed IS NOT NULL THEN 'real_only'
                    ELSE 'unknown'
                END as status_bucket
            FROM plan_latest p
            FULL OUTER JOIN real_aggregated r ON (
                p.country = r.country
                AND p.month = r.month
                AND p.city_norm_plan_effective = r.city_norm
                AND p.lob_base = r.lob_base
                AND p.segment = r.segment
            )
            ORDER BY COALESCE(p.month, r.month) DESC, 
                     COALESCE(p.country, r.country), 
                     COALESCE(p.city_norm_plan_effective, r.city_norm),
                     COALESCE(p.lob_base, r.lob_base),
                     COALESCE(p.segment, r.segment)
            """,
            
            # 4. Vista de alertas
            """
            DROP VIEW IF EXISTS ops.v_plan_vs_real_alerts_monthly_latest CASCADE;
            CREATE VIEW ops.v_plan_vs_real_alerts_monthly_latest AS
            WITH alerts_base AS (
                SELECT 
                    country,
                    month,
                    city_norm_real,
                    lob_base,
                    segment,
                    plan_version,
                    -- PLAN
                    projected_trips,
                    projected_revenue,
                    -- REAL
                    trips_real_completed,
                    revenue_real_proxy,
                    -- GAPS
                    gap_trips,
                    gap_revenue_proxy,
                    -- GAPS porcentuales
                    CASE 
                        WHEN projected_trips > 0 
                        THEN (gap_trips::NUMERIC / projected_trips) * 100
                        ELSE NULL
                    END as gap_trips_pct,
                    CASE 
                        WHEN projected_revenue > 0 
                        THEN (gap_revenue_proxy::NUMERIC / projected_revenue) * 100
                        ELSE NULL
                    END as gap_revenue_pct
                FROM ops.v_plan_vs_real_monthly_latest
                WHERE has_plan = TRUE AND has_real = TRUE
            )
            SELECT 
                country,
                month,
                city_norm_real,
                lob_base,
                segment,
                plan_version,
                projected_trips,
                projected_revenue,
                trips_real_completed,
                revenue_real_proxy,
                gap_trips,
                gap_revenue_proxy,
                gap_trips_pct,
                gap_revenue_pct,
                -- ALERT LEVEL
                CASE
                    WHEN gap_revenue_pct IS NOT NULL AND gap_revenue_pct <= -15 THEN 'CRITICO'
                    WHEN gap_trips_pct IS NOT NULL AND gap_trips_pct <= -20 THEN 'CRITICO'
                    WHEN gap_revenue_pct IS NOT NULL AND gap_revenue_pct <= -8 THEN 'MEDIO'
                    WHEN gap_trips_pct IS NOT NULL AND gap_trips_pct <= -10 THEN 'MEDIO'
                    ELSE 'OK'
                END as alert_level
            FROM alerts_base
            ORDER BY 
                CASE
                    WHEN gap_revenue_pct IS NOT NULL AND gap_revenue_pct <= -15 THEN 1
                    WHEN gap_trips_pct IS NOT NULL AND gap_trips_pct <= -20 THEN 1
                    WHEN gap_revenue_pct IS NOT NULL AND gap_revenue_pct <= -8 THEN 2
                    WHEN gap_trips_pct IS NOT NULL AND gap_trips_pct <= -10 THEN 2
                    ELSE 3
                END,
                month DESC,
                country,
                city_norm_real
            """
        ]
        
        for i, sql in enumerate(sql_statements, 1):
            try:
                cursor.execute(sql)
                conn.commit()
                print(f"[OK] Vista {i} creada")
            except Exception as e:
                print(f"[ERROR] Error creando vista {i}: {e}")
                conn.rollback()
                raise
        
        cursor.close()
        print("[OK] Todas las vistas creadas exitosamente")

if __name__ == "__main__":
    main()
