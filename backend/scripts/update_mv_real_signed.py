#!/usr/bin/env python3
"""
Actualiza MV real para corregir signo de revenue_real_yego.
Crea ops.mv_real_trips_monthly_v3 y hace swap seguro sin CASCADE.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_mv_real_signed():
    print("=" * 80)
    print("ACTUALIZANDO MV REAL: SIGNO REVENUE_REAL_YEGO")
    print("=" * 80)

    init_db_pool()

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Aumentar timeout
            cursor.execute("SET statement_timeout = '7200000ms'")
            conn.commit()

            print("\n1. Creando ops.mv_real_trips_monthly_v3...")
            cursor.execute("""
                CREATE MATERIALIZED VIEW ops.mv_real_trips_monthly_v3 AS
                WITH real_aggregated AS (
                    SELECT 
                        DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE as month,
                        t.park_id,
                        t.tipo_servicio as lob_raw,
                        CASE 
                            WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                            ELSE 'b2c'
                        END as segment,

                        COUNT(*) as trips_real_completed,
                        COUNT(DISTINCT t.conductor_id) as active_drivers_real,

                        -- Commission signed (contable, negativo por convención)
                        SUM(COALESCE(NULLIF(t.comision_empresa_asociada, 0), 0)) as commission_yego_signed,

                        SUM(
                            COALESCE(t.efectivo, 0) +
                            COALESCE(t.tarjeta, 0) +
                            COALESCE(t.pago_corporativo, 0)
                        ) as gmv_passenger_paid,

                        SUM(
                            COALESCE(t.efectivo, 0) +
                            COALESCE(t.tarjeta, 0) +
                            COALESCE(t.pago_corporativo, 0) +
                            COALESCE(t.propina, 0) +
                            COALESCE(t.otros_pagos, 0) +
                            COALESCE(t.bonificaciones, 0) +
                            COALESCE(t.promocion, 0)
                        ) as gmv_total,

                        AVG(t.precio_yango_pro) FILTER (WHERE t.precio_yango_pro IS NOT NULL) as avg_ticket_real

                    FROM public.trips_all t
                    WHERE t.condicion = 'Completado'
                    AND t.fecha_inicio_viaje IS NOT NULL
                    GROUP BY 
                        DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE,
                        t.park_id,
                        t.tipo_servicio,
                        CASE 
                            WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                            ELSE 'b2c'
                        END
                ),
                dim_park_unique AS (
                    SELECT DISTINCT ON (park_id)
                        park_id,
                        country,
                        city,
                        default_line_of_business
                    FROM dim.dim_park
                    ORDER BY park_id, country, city, default_line_of_business
                ),
                joined_data AS (
                    SELECT 
                        r.month,
                        COALESCE(dp.country, '') as country,
                        COALESCE(dp.city, '') as city,
                        LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm,
                        COALESCE(dp.default_line_of_business, r.lob_raw) as lob_base,
                        r.segment,

                        r.trips_real_completed,
                        r.active_drivers_real,
                        r.avg_ticket_real,
                        r.commission_yego_signed,
                        r.gmv_passenger_paid,
                        r.gmv_total
                    FROM real_aggregated r
                    LEFT JOIN dim_park_unique dp ON r.park_id = dp.park_id
                )
                -- Agregación final por grano canónico
                SELECT 
                    month,
                    country,
                    MAX(city) as city,
                    city_norm,
                    lob_base,
                    segment,

                    SUM(trips_real_completed) as trips_real_completed,
                    SUM(active_drivers_real) as active_drivers_real,
                    AVG(avg_ticket_real) FILTER (WHERE avg_ticket_real IS NOT NULL) as avg_ticket_real,

                    SUM(commission_yego_signed) as commission_yego_signed,
                    (-1 * SUM(commission_yego_signed)) as revenue_real_yego,

                    SUM(gmv_passenger_paid) as gmv_passenger_paid,
                    SUM(gmv_total) as gmv_total,

                    CASE 
                        WHEN SUM(active_drivers_real) > 0 
                        THEN SUM(trips_real_completed)::NUMERIC / SUM(active_drivers_real)
                        ELSE NULL
                    END as trips_per_driver,

                    CASE
                        WHEN SUM(gmv_passenger_paid) > 0
                        THEN ROUND(
                            (-1 * SUM(commission_yego_signed)) / NULLIF(SUM(gmv_passenger_paid), 0),
                            4
                        )
                        ELSE NULL
                    END as take_rate_yego,

                    NOW() as refreshed_at,

                    (month = DATE_TRUNC('month', NOW())::DATE) as is_partial_real

                FROM joined_data
                GROUP BY month, country, city_norm, lob_base, segment;
            """)
            conn.commit()
            print("   [OK] MV v3 creada")

            print("\n2. Creando indices en v3...")
            indices = [
                ("idx_mv_real_trips_monthly_v3_month", "month"),
                ("idx_mv_real_trips_monthly_v3_country_city_lob_seg_month", "country, city_norm, lob_base, segment, month"),
                ("idx_mv_real_trips_monthly_v3_country", "country"),
                ("idx_mv_real_trips_monthly_v3_city_norm", "city_norm")
            ]
            for idx_name, cols in indices:
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name}
                    ON ops.mv_real_trips_monthly_v3({cols});
                """)
                print(f"   [OK] Indice {idx_name} creado")
            conn.commit()

            print("\n3. Poblando MV v3...")
            cursor.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly_v3")
            conn.commit()
            print("   [OK] MV v3 poblada")

            print("\n4. Swap seguro (sin CASCADE)...")
            cursor.execute("BEGIN")
            cursor.execute("""
                ALTER MATERIALIZED VIEW ops.mv_real_trips_monthly
                RENAME TO mv_real_trips_monthly_old_signed;
            """)
            cursor.execute("""
                ALTER MATERIALIZED VIEW ops.mv_real_trips_monthly_v3
                RENAME TO mv_real_trips_monthly;
            """)
            cursor.execute("""
                CREATE OR REPLACE FUNCTION ops.refresh_real_trips_monthly()
                RETURNS void AS $$
                BEGIN
                    REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly;
                END;
                $$ LANGUAGE plpgsql;
            """)
            cursor.execute("COMMIT")
            print("   [OK] Swap completado")

            cursor.close()
            print("\n" + "=" * 80)
            print("ACTUALIZACION COMPLETADA")
            print("=" * 80)
            return 0

    except Exception as e:
        logger.error(f"Error al actualizar MV: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(update_mv_real_signed())
