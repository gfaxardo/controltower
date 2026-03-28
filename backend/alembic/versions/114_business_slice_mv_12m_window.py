"""
BUSINESS_SLICE: ventana MV 12 meses (menor uso de temp/disco en REFRESH).

Si 36m agota disco del servidor PostgreSQL, esta migración reduce el alcance del agregado mensual.
"""
from alembic import op

revision = "114_business_slice_mv_12m_window"
down_revision = "113_business_slice_enriched_pipeline"
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
            'NOT_IMPLEMENTED'::text AS connected_only_drivers_status,
            avg(r.ticket) FILTER (
                WHERE r.completed_flag AND r.ticket IS NOT NULL
            ) AS avg_ticket,
            CASE
                WHEN sum(r.total_fare) FILTER (
                    WHERE r.completed_flag
                      AND r.total_fare IS NOT NULL
                      AND r.total_fare > 0
                ) > 0
                THEN sum(r.revenue_yego_net) FILTER (
                    WHERE r.completed_flag
                      AND r.total_fare IS NOT NULL
                      AND r.total_fare > 0
                )
                    / sum(r.total_fare) FILTER (
                        WHERE r.completed_flag
                          AND r.total_fare IS NOT NULL
                          AND r.total_fare > 0
                    )
                ELSE NULL
            END AS commission_pct,
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
          AND r.trip_month >= date_trunc('month', (CURRENT_DATE - INTERVAL '12 months')::date)::date
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
        'Agregado mensual BUSINESS_SLICE; ventana 12 meses (reduce temp en REFRESH). commission_pct = SUM(revenue)/SUM(total_fare) con total_fare>0.'
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


def downgrade() -> None:
    raise NotImplementedError("Downgrade 114: aplicar 113 manualmente si aplica.")
