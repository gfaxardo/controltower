"""
OV2-D.1 — Register Omniview V2 fact tables in ops.serving_registry.

Registers the 4 canonical fact tables for Omniview V2 freshness governance:
- ops.driver_day_slice_fact (Driver Bridge)
- ops.real_business_slice_day_fact (Day Fact)
- ops.real_business_slice_week_fact (Week Fact)
- ops.real_business_slice_month_fact (Month Fact)

Ownership governance pre-audited in OWNERSHIP_CERTIFICATION.md v1.5.0.
Preflight: OMNIVIEW_V2_FRESHNESS_REGISTRY_PREFLIGHT.md v1.0.0.

No DDL changes. INSERT only. Idempotent via ON CONFLICT DO UPDATE.
No refresh executed. Freshness is NOT certified — registered pending validation.

down_revision: 220_lg_exp_1d_driver_explorer_fact
"""
from alembic import op

revision = "221_ov2_d1_serving_registry"
down_revision = "220_lg_exp_1d_driver_explorer_fact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO ops.serving_registry
            (serving_key, entity_name, grain, plan_version, coverage_scope,
             source_dependencies, fallback_allowed, runtime_protected, active_flag)
        VALUES
        (
            'omniview_v2_driver_bridge',
            'ops.driver_day_slice_fact',
            'daily',
            NULL,
            '{"dimensions":["country","city","park_id","business_slice_name","driver_id"],"metrics":["completed_trips","cancelled_trips","active_drivers"]}'::jsonb,
            '["public.trips_2026","dim.dim_park","ops.business_slice_mapping_rules"]'::jsonb,
            false,
            true,
            true
        ),
        (
            'omniview_v2_real_business_slice_day_fact',
            'ops.real_business_slice_day_fact',
            'daily',
            NULL,
            '{"dimensions":["country","city","business_slice_name","fleet_display_name"],"metrics":["trips_completed","trips_cancelled","active_drivers","revenue_yego_final","revenue_yego_net","avg_ticket","trips_per_driver","commission_pct"]}'::jsonb,
            '["ops.driver_day_slice_fact","ops.real_business_slice_day_fact"]'::jsonb,
            false,
            true,
            true
        ),
        (
            'omniview_v2_real_business_slice_week_fact',
            'ops.real_business_slice_week_fact',
            'weekly',
            NULL,
            '{"dimensions":["country","city","business_slice_name","fleet_display_name"],"metrics":["trips_completed","trips_cancelled","active_drivers","revenue_yego_final","revenue_yego_net","avg_ticket","trips_per_driver","commission_pct","empty_supply_drivers","total_drivers","completed_rate_pct"]}'::jsonb,
            '["ops.real_business_slice_day_fact","ops.driver_day_slice_fact"]'::jsonb,
            false,
            true,
            true
        ),
        (
            'omniview_v2_real_business_slice_month_fact',
            'ops.real_business_slice_month_fact',
            'monthly',
            NULL,
            '{"dimensions":["country","city","business_slice_name","fleet_display_name"],"metrics":["trips_completed","trips_cancelled","active_drivers","revenue_yego_final","revenue_yego_net","avg_ticket","trips_per_driver","commission_pct"]}'::jsonb,
            '["ops.real_business_slice_day_fact","ops.driver_day_slice_fact"]'::jsonb,
            false,
            true,
            true
        )
        ON CONFLICT (serving_key) DO UPDATE SET
            entity_name = EXCLUDED.entity_name,
            grain = EXCLUDED.grain,
            coverage_scope = EXCLUDED.coverage_scope,
            source_dependencies = EXCLUDED.source_dependencies,
            fallback_allowed = EXCLUDED.fallback_allowed,
            runtime_protected = EXCLUDED.runtime_protected,
            active_flag = EXCLUDED.active_flag,
            updated_at = NOW()
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM ops.serving_registry
        WHERE serving_key IN (
            'omniview_v2_driver_bridge',
            'omniview_v2_real_business_slice_day_fact',
            'omniview_v2_real_business_slice_week_fact',
            'omniview_v2_real_business_slice_month_fact'
        )
    """)
