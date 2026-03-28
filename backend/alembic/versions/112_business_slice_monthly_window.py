"""
BUSINESS_SLICE: ventana en MV mensual para refresco viable en BD grandes.

La agregación completa sobre toda la historia puede exceder timeouts operativos.
Grano mensual Fase 1 limitado a últimos 36 meses (ajustable en migración futura).
"""
from alembic import op

revision = "112_business_slice_monthly_window"
down_revision = "111_business_slice_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_business_slice_join_stub CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_business_slice_monthly CASCADE")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_business_slice_monthly AS
        SELECT
            r.trip_month AS month,
            r.country,
            r.city,
            r.business_slice_name,
            r.fleet_display_name,
            r.is_subfleet,
            r.subfleet_name,
            r.parent_fleet_name,
            count(*) FILTER (WHERE r.completed_flag) AS trips_completed,
            count(*) FILTER (WHERE r.cancelled_flag) AS trips_cancelled,
            count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) AS active_drivers,
            NULL::bigint AS connected_only_drivers,
            avg(r.ticket) FILTER (
                WHERE r.completed_flag AND r.ticket IS NOT NULL
            ) AS avg_ticket,
            avg(
                CASE
                    WHEN r.completed_flag
                         AND r.gmv_passenger_paid IS NOT NULL
                         AND r.gmv_passenger_paid > 0
                         AND r.revenue_yego_net IS NOT NULL
                    THEN r.revenue_yego_net / r.gmv_passenger_paid
                END
            ) AS commission_pct,
            CASE
                WHEN count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) > 0
                THEN (
                    count(*) FILTER (WHERE r.completed_flag)::numeric
                    / count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)
                )
                ELSE NULL
            END AS trips_per_driver,
            sum(r.revenue_yego_net) FILTER (WHERE r.completed_flag) AS revenue_yego_net,
            CASE
                WHEN sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0) > 0
                THEN sum(r.ticket) FILTER (WHERE r.completed_flag AND r.km > 0)
                    / sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0)
                ELSE NULL
            END AS precio_km,
            CASE
                WHEN sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0) > 0
                THEN sum(r.duration_minutes) FILTER (WHERE r.completed_flag AND r.km > 0)
                    / sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0)
                ELSE NULL
            END AS tiempo_km,
            CASE
                WHEN sum(r.duration_minutes) FILTER (
                    WHERE r.completed_flag AND r.duration_minutes > 0
                ) > 0
                THEN count(*) FILTER (WHERE r.completed_flag)::numeric
                    / (
                        sum(r.duration_minutes) FILTER (
                            WHERE r.completed_flag AND r.duration_minutes > 0
                        ) / 60.0
                    )
                ELSE NULL
            END AS completados_por_hora,
            CASE
                WHEN sum(r.duration_minutes) FILTER (
                    WHERE r.completed_flag AND r.duration_minutes > 0
                ) > 0
                THEN count(*) FILTER (WHERE r.cancelled_flag)::numeric
                    / (
                        sum(r.duration_minutes) FILTER (
                            WHERE r.completed_flag AND r.duration_minutes > 0
                        ) / 60.0
                    )
                ELSE NULL
            END AS cancelados_por_hora,
            now() AS refreshed_at
        FROM ops.v_real_trips_business_slice_resolved r
        WHERE r.resolution_status = 'resolved'
          AND r.trip_month IS NOT NULL
          AND r.business_slice_name IS NOT NULL
          AND r.trip_month >= date_trunc('month', (CURRENT_DATE - INTERVAL '36 months')::date)::date
        GROUP BY
            r.trip_month,
            r.country,
            r.city,
            r.business_slice_name,
            r.fleet_display_name,
            r.is_subfleet,
            r.subfleet_name,
            r.parent_fleet_name
        WITH NO DATA
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_bs_monthly_dims
        ON ops.mv_real_business_slice_monthly (month, country, city, business_slice_name)
    """)
    op.execute("""
        COMMENT ON MATERIALIZED VIEW ops.mv_real_business_slice_monthly IS
        'Agregado mensual BUSINESS_SLICE. Ventana: trip_month >= inicio del mes (hoy - 36 meses). Ampliar vía migración si se requiere historia completa.'
    """)
    op.execute("""
        CREATE VIEW ops.v_plan_business_slice_join_stub AS
        SELECT DISTINCT
            m.country,
            m.city,
            m.business_slice_name,
            m.month,
            'pending_plan_key_country_city_business_slice_month'::text AS join_contract,
            NULL::numeric AS plan_value_placeholder
        FROM ops.mv_real_business_slice_monthly m
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_plan_business_slice_join_stub IS
        'Contrato futuro Plan vs Real por BUSINESS_SLICE: clave country + city + business_slice_name + month.'
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_business_slice_monthly CASCADE")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_business_slice_monthly AS
        SELECT
            r.trip_month AS month,
            r.country,
            r.city,
            r.business_slice_name,
            r.fleet_display_name,
            r.is_subfleet,
            r.subfleet_name,
            r.parent_fleet_name,
            count(*) FILTER (WHERE r.completed_flag) AS trips_completed,
            count(*) FILTER (WHERE r.cancelled_flag) AS trips_cancelled,
            count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) AS active_drivers,
            NULL::bigint AS connected_only_drivers,
            avg(r.ticket) FILTER (
                WHERE r.completed_flag AND r.ticket IS NOT NULL
            ) AS avg_ticket,
            avg(
                CASE
                    WHEN r.completed_flag
                         AND r.gmv_passenger_paid IS NOT NULL
                         AND r.gmv_passenger_paid > 0
                         AND r.revenue_yego_net IS NOT NULL
                    THEN r.revenue_yego_net / r.gmv_passenger_paid
                END
            ) AS commission_pct,
            CASE
                WHEN count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) > 0
                THEN (
                    count(*) FILTER (WHERE r.completed_flag)::numeric
                    / count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)
                )
                ELSE NULL
            END AS trips_per_driver,
            sum(r.revenue_yego_net) FILTER (WHERE r.completed_flag) AS revenue_yego_net,
            CASE
                WHEN sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0) > 0
                THEN sum(r.ticket) FILTER (WHERE r.completed_flag AND r.km > 0)
                    / sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0)
                ELSE NULL
            END AS precio_km,
            CASE
                WHEN sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0) > 0
                THEN sum(r.duration_minutes) FILTER (WHERE r.completed_flag AND r.km > 0)
                    / sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0)
                ELSE NULL
            END AS tiempo_km,
            CASE
                WHEN sum(r.duration_minutes) FILTER (
                    WHERE r.completed_flag AND r.duration_minutes > 0
                ) > 0
                THEN count(*) FILTER (WHERE r.completed_flag)::numeric
                    / (
                        sum(r.duration_minutes) FILTER (
                            WHERE r.completed_flag AND r.duration_minutes > 0
                        ) / 60.0
                    )
                ELSE NULL
            END AS completados_por_hora,
            CASE
                WHEN sum(r.duration_minutes) FILTER (
                    WHERE r.completed_flag AND r.duration_minutes > 0
                ) > 0
                THEN count(*) FILTER (WHERE r.cancelled_flag)::numeric
                    / (
                        sum(r.duration_minutes) FILTER (
                            WHERE r.completed_flag AND r.duration_minutes > 0
                        ) / 60.0
                    )
                ELSE NULL
            END AS cancelados_por_hora,
            now() AS refreshed_at
        FROM ops.v_real_trips_business_slice_resolved r
        WHERE r.resolution_status = 'resolved'
          AND r.trip_month IS NOT NULL
          AND r.business_slice_name IS NOT NULL
        GROUP BY
            r.trip_month,
            r.country,
            r.city,
            r.business_slice_name,
            r.fleet_display_name,
            r.is_subfleet,
            r.subfleet_name,
            r.parent_fleet_name
        WITH NO DATA
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_bs_monthly_dims
        ON ops.mv_real_business_slice_monthly (month, country, city, business_slice_name)
    """)
