"""
156 — Ownership Serving Fact Foundation (Fase 0.2)

Crea la capa serving ownership-aware que conecta plan canónico + real facts
con la tabla de governance de ownership (ops.projection_ownership).

NO modifica:
- Omniview
- Plan vs Real
- MVs existentes
- UI

Crea:
- ops.mv_ownership_serving_fact: MV mensual con plan/real/ownership a grain canónico
- ops.refresh_ownership_serving_fact(boolean): función de refresh controlada
- Índices de performance
- Registro en serving_registry

Grain: (plan_version, period, country, city, lob_base, jefe_producto)
Fuentes: ops.plan_trips_monthly + ops.real_business_slice_month_fact + ops.projection_ownership
Bridge: ops.control_loop_plan_line_to_business_slice (plan LOB → business_slice)

down_revision: 155_projection_ownership_governance
"""

from alembic import op

revision = "156_ownership_serving_fact_foundation"
down_revision = "155_projection_ownership_governance"
branch_labels = None
depends_on = None


_MV_SQL = """
WITH
plan_base AS (
    SELECT
        ptm.plan_version,
        ptm.month AS period,
        ptm.country,
        ptm.city,
        ptm.lob_base,
        CASE
            WHEN COUNT(DISTINCT ptm.segment) > 1 THEN 'b2b+b2c'
            ELSE MAX(ptm.segment)
        END AS segment,
        SUM(ptm.projected_trips) AS projected_trips,
        SUM(ptm.projected_drivers) AS projected_drivers,
        CASE
            WHEN SUM(ptm.projected_trips) > 0 AND COUNT(*) > 0
            THEN SUM(ptm.projected_revenue) / SUM(ptm.projected_trips)
            ELSE NULL
        END AS projected_ticket,
        SUM(ptm.projected_revenue) AS projected_revenue,
        CASE
            WHEN SUM(ptm.projected_drivers) > 0
            THEN SUM(ptm.projected_trips)::numeric / SUM(ptm.projected_drivers)
            ELSE NULL
        END AS projected_trips_per_driver,
        CASE
            WHEN TRIM(LOWER(ptm.country)) = 'co' THEN 'colombia'
            WHEN TRIM(LOWER(ptm.country)) = 'pe' THEN 'peru'
            ELSE LOWER(TRIM(ptm.country))
        END AS country_real,
        TRIM(LOWER(ptm.city)) AS city_real,
        REPLACE(TRIM(LOWER(ptm.lob_base)), ' ', '_') AS lob_base_normalized
    FROM ops.plan_trips_monthly ptm
    GROUP BY ptm.plan_version, ptm.month, ptm.country, ptm.city, ptm.lob_base
),
ownership AS (
    SELECT DISTINCT ON (plan_version_key, country, city, linea_negocio_canonica)
        plan_version_key,
        country AS own_country,
        city AS own_city,
        linea_negocio_canonica,
        jefe_producto,
        producto,
        estado,
        conflict_detected,
        conflict_detail
    FROM ops.projection_ownership
),
lob_slice_bridge AS (
    SELECT
        plan_line_key,
        business_slice_name
    FROM ops.control_loop_plan_line_to_business_slice
    WHERE active = true
),
real_agg AS (
    SELECT
        month,
        country,
        city,
        business_slice_name,
        SUM(trips_completed) AS trips_completed,
        SUM(trips_cancelled) AS trips_cancelled,
        SUM(active_drivers) AS active_drivers,
        CASE
            WHEN SUM(ticket_sum_completed) > 0 AND SUM(ticket_count_completed) > 0
            THEN SUM(ticket_sum_completed) / SUM(ticket_count_completed)
            ELSE NULL
        END AS avg_ticket,
        CASE
            WHEN SUM(total_fare_completed_positive_sum) > 0
            THEN SUM(revenue_yego_net) / SUM(total_fare_completed_positive_sum)
            ELSE NULL
        END AS commission_pct,
        SUM(revenue_yego_net) AS revenue_yego_net,
        MAX(refreshed_at) AS refreshed_at
    FROM ops.real_business_slice_month_fact
    WHERE is_subfleet = false
    GROUP BY month, country, city, business_slice_name
),
plan_owned AS (
    SELECT
        p.plan_version,
        p.period,
        p.country,
        p.city,
        p.lob_base,
        p.segment,
        p.country_real,
        p.city_real,
        p.lob_base_normalized,
        p.projected_trips,
        p.projected_drivers,
        p.projected_ticket,
        p.projected_revenue,
        p.projected_trips_per_driver,
        o.jefe_producto,
        o.producto AS producto_plan,
        o.estado AS estado_validacion,
        o.conflict_detected,
        o.conflict_detail,
        b.business_slice_name AS resolved_business_slice,
        CASE
            WHEN o.jefe_producto IS NOT NULL AND o.conflict_detected = true THEN 'conflicting'
            WHEN o.jefe_producto IS NOT NULL THEN 'assigned'
            ELSE 'missing'
        END AS ownership_assignment,
        CASE
            WHEN o.linea_negocio_canonica IS NULL THEN 'no_ownership_record'
            WHEN o.jefe_producto IS NULL OR TRIM(o.jefe_producto) = '' THEN 'no_owner_named'
            WHEN o.conflict_detected THEN 'conflict_detected'
            ELSE 'ok'
        END AS ownership_quality
    FROM plan_base p
    LEFT JOIN ownership o
        ON o.plan_version_key = p.plan_version
        AND unaccent(TRIM(LOWER(COALESCE(o.own_country, '')))) = unaccent(TRIM(LOWER(COALESCE(p.country, ''))))
        AND unaccent(TRIM(LOWER(COALESCE(o.own_city, '')))) = unaccent(TRIM(LOWER(COALESCE(p.city, ''))))
        AND TRIM(LOWER(o.linea_negocio_canonica)) = p.lob_base_normalized
    LEFT JOIN lob_slice_bridge b
        ON TRIM(LOWER(b.plan_line_key)) = TRIM(LOWER(p.lob_base_normalized))
),
with_real AS (
    SELECT
        po.plan_version,
        po.period,
        po.country,
        po.city,
        po.lob_base,
        po.segment,
        po.jefe_producto,
        po.producto_plan,
        po.estado_validacion,
        po.ownership_assignment,
        po.ownership_quality,
        po.conflict_detected,
        po.conflict_detail,
        po.projected_trips,
        po.projected_drivers,
        po.projected_ticket,
        po.projected_revenue,
        po.projected_trips_per_driver,
        COALESCE(r.trips_completed, 0) AS real_trips,
        COALESCE(r.trips_cancelled, 0) AS real_trips_cancelled,
        r.active_drivers AS real_active_drivers,
        r.avg_ticket AS real_avg_ticket,
        r.commission_pct AS real_commission_pct,
        COALESCE(r.revenue_yego_net, 0) AS real_revenue,
        CASE
            WHEN po.projected_trips > 0 THEN
                ROUND((COALESCE(r.trips_completed, 0)::numeric / po.projected_trips) * 100, 2)
            ELSE NULL
        END AS execution_pct_trips,
        CASE
            WHEN po.projected_revenue > 0 THEN
                ROUND((COALESCE(r.revenue_yego_net, 0)::numeric / po.projected_revenue) * 100, 2)
            ELSE NULL
        END AS execution_pct_revenue,
        COALESCE(r.trips_completed, 0) - po.projected_trips AS gap_trips,
        COALESCE(r.revenue_yego_net, 0) - po.projected_revenue AS gap_revenue,
        CASE
            WHEN po.projected_trips IS NULL OR po.projected_trips = 0 THEN 'no_target'
            WHEN COALESCE(r.trips_completed, 0) >= po.projected_trips THEN 'on_track'
            WHEN COALESCE(r.trips_completed, 0) >= po.projected_trips * 0.9 THEN 'at_risk'
            ELSE 'behind'
        END AS momentum_status,
        r.refreshed_at AS real_fact_refreshed_at
    FROM plan_owned po
    LEFT JOIN real_agg r
        ON r.month = po.period
        AND unaccent(TRIM(LOWER(COALESCE(r.country, '')))) = unaccent(po.country_real)
        AND unaccent(TRIM(LOWER(COALESCE(r.city, '')))) = unaccent(po.city_real)
        AND (
            TRIM(LOWER(COALESCE(r.business_slice_name, ''))) = TRIM(LOWER(COALESCE(po.resolved_business_slice, '')))
            OR (
                po.resolved_business_slice IS NULL
                AND TRIM(LOWER(COALESCE(r.business_slice_name, ''))) = TRIM(LOWER(po.lob_base))
            )
        )
),
with_mom AS (
    SELECT
        *,
        LAG(real_trips) OVER (
            PARTITION BY plan_version, TRIM(LOWER(COALESCE(country, ''))),
                         TRIM(LOWER(COALESCE(city, ''))),
                         TRIM(LOWER(COALESCE(jefe_producto, 'sin_owner')))
            ORDER BY period
        ) AS real_trips_prev_month,
        LAG(real_revenue) OVER (
            PARTITION BY plan_version, TRIM(LOWER(COALESCE(country, ''))),
                         TRIM(LOWER(COALESCE(city, ''))),
                         TRIM(LOWER(COALESCE(jefe_producto, 'sin_owner')))
            ORDER BY period
        ) AS real_revenue_prev_month,
        LAG(projected_trips) OVER (
            PARTITION BY plan_version, TRIM(LOWER(COALESCE(country, ''))),
                         TRIM(LOWER(COALESCE(city, ''))),
                         TRIM(LOWER(COALESCE(jefe_producto, 'sin_owner')))
            ORDER BY period
        ) AS projected_trips_prev_month,
        LAG(projected_revenue) OVER (
            PARTITION BY plan_version, TRIM(LOWER(COALESCE(country, ''))),
                         TRIM(LOWER(COALESCE(city, ''))),
                         TRIM(LOWER(COALESCE(jefe_producto, 'sin_owner')))
            ORDER BY period
        ) AS projected_revenue_prev_month
    FROM with_real
)
SELECT
    plan_version,
    period,
    to_char(period, 'YYYY-MM') AS month,
    country,
    city,
    city AS city_norm,
    lob_base,
    segment,
    jefe_producto,
    producto_plan,
    estado_validacion,
    ownership_assignment,
    ownership_quality,
    conflict_detected,
    conflict_detail,
    projected_trips,
    projected_drivers,
    projected_ticket,
    projected_revenue,
    projected_trips_per_driver,
    real_trips,
    real_trips_cancelled,
    real_active_drivers,
    real_avg_ticket,
    real_commission_pct,
    real_revenue,
    execution_pct_trips,
    execution_pct_revenue,
    gap_trips,
    gap_revenue,
    momentum_status,
    -- MoM real growth
    CASE
        WHEN real_trips_prev_month > 0 THEN
            ROUND(((real_trips - real_trips_prev_month)::numeric / real_trips_prev_month) * 100, 2)
        ELSE NULL
    END AS mom_pct_real_trips,
    CASE
        WHEN real_revenue_prev_month > 0 THEN
            ROUND(((real_revenue - real_revenue_prev_month)::numeric / real_revenue_prev_month) * 100, 2)
        ELSE NULL
    END AS mom_pct_real_revenue,
    -- MoM plan change
    CASE
        WHEN projected_trips_prev_month > 0 THEN
            ROUND(((projected_trips - projected_trips_prev_month)::numeric / projected_trips_prev_month) * 100, 2)
        ELSE NULL
    END AS mom_pct_projected_trips,
    -- MoM execution delta (change in execution_pct)
    CASE
        WHEN real_trips_prev_month > 0 AND projected_trips_prev_month > 0 AND projected_trips > 0 THEN
            ROUND(
                ((real_trips::numeric / projected_trips) -
                 (real_trips_prev_month::numeric / projected_trips_prev_month)) * 100, 2
            )
        ELSE NULL
    END AS mom_delta_execution_pp,
    real_fact_refreshed_at,
    now() AS refreshed_at
FROM with_mom
"""


def upgrade() -> None:
    op.execute("SET statement_timeout = 0")

    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_ownership_serving_fact CASCADE")
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_ownership_serving_fact(boolean)")

    op.execute(
        f"""
        CREATE MATERIALIZED VIEW ops.mv_ownership_serving_fact AS
        {_MV_SQL}
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_ownership_serving_fact_grain
        ON ops.mv_ownership_serving_fact (
            plan_version,
            period,
            COALESCE(country, ''),
            COALESCE(city, ''),
            COALESCE(lob_base, ''),
            COALESCE(segment, ''),
            COALESCE(jefe_producto, 'sin_owner')
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mv_osf_period ON ops.mv_ownership_serving_fact (period)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mv_osf_jefe ON ops.mv_ownership_serving_fact (jefe_producto)"
        " WHERE jefe_producto IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mv_osf_country_city_lob "
        "ON ops.mv_ownership_serving_fact (country, city, lob_base)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mv_osf_ownership_assignment "
        "ON ops.mv_ownership_serving_fact (ownership_assignment)"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ops.refresh_ownership_serving_fact(
            p_concurrent boolean DEFAULT TRUE
        )
        RETURNS void
        LANGUAGE plpgsql
        AS $f$
        BEGIN
            IF p_concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_ownership_serving_fact;
            ELSE
                REFRESH MATERIALIZED VIEW ops.mv_ownership_serving_fact;
            END IF;
        END;
        $f$
        """
    )

    op.execute(
        "COMMENT ON MATERIALIZED VIEW ops.mv_ownership_serving_fact IS "
        "'Fase 0.2 — Ownership Serving Fact: plan + real + ownership a grain (plan_version, period, country, city, lob_base, jefe_producto). "
        "NO se expone en Omniview todavía. Base para Ownership Perspective futura.'"
    )

    op.execute(
        "COMMENT ON FUNCTION ops.refresh_ownership_serving_fact(boolean) IS "
        "'Refresh controlado de ops.mv_ownership_serving_fact. p_concurrent=true para refresco sin bloqueo. "
        "Ejecutar tras upload de plan + refresh de real facts.'"
    )

    op.execute(
        """
        INSERT INTO ops.serving_registry
            (serving_key, entity_name, grain, plan_version, coverage_scope,
             source_dependencies, fallback_allowed, runtime_protected, active_flag)
        VALUES (
            'ownership_serving_monthly',
            'Ownership Serving Monthly Fact',
            'monthly',
            NULL,
            '{"dimensions":["country","city","lob_base","jefe_producto"],"metrics":["trips","revenue","execution"]}'::jsonb,
            '["ops.plan_trips_monthly","ops.real_business_slice_month_fact","ops.projection_ownership"]'::jsonb,
            false,
            true,
            true
        )
        ON CONFLICT (serving_key) DO UPDATE SET
            source_dependencies = EXCLUDED.source_dependencies,
            coverage_scope = EXCLUDED.coverage_scope,
            updated_at = NOW()
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_ownership_serving_fact(boolean)")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_ownership_serving_fact CASCADE")
    op.execute(
        "DELETE FROM ops.serving_registry WHERE serving_key = 'ownership_serving_monthly'"
    )
