"""
170 — YEGO Lima Growth: State-Based Loyalty Architecture (Fase 2D-R)

Creates:
- growth.yango_lima_driver_state_snapshot
- growth.yango_lima_program_eligibility_daily
- growth.yango_lima_daily_opportunity_list

Additive. No DROP.
Legacy tables (segment_snapshot, actionable_list_daily) preserved.

down_revision: 169_yego_lima_daily_pipeline_foundation
"""

from alembic import op

revision = "170_yego_lima_state_based_loyalty_architecture"
down_revision = "169_yego_lima_daily_pipeline_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    # ── Table 1: Driver State Snapshot ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_driver_state_snapshot (
            snapshot_date           date NOT NULL,
            driver_profile_id       text NOT NULL,

            lifecycle_state         text NOT NULL,
            performance_state       text NOT NULL,
            retention_state         text NOT NULL,

            completed_orders_day    integer NOT NULL DEFAULT 0,
            completed_orders_week   integer NOT NULL DEFAULT 0,
            supply_hours_day        numeric(18,4) NOT NULL DEFAULT 0,
            supply_hours_week       numeric(18,4) NOT NULL DEFAULT 0,
            trips_per_supply_hour_week numeric(18,4) NULL,

            avg_orders_4w           numeric(18,4) NULL,
            avg_orders_12w          numeric(18,4) NULL,
            best_week_12w           integer NULL,
            historical_band         text NULL,

            weekly_trips_target     integer NOT NULL,
            distance_to_weekly_target integer NULL,

            new_driver_flag         boolean NOT NULL DEFAULT false,
            reactivated_flag        boolean NOT NULL DEFAULT false,
            recoverable_flag        boolean NOT NULL DEFAULT false,
            declining_flag          boolean NOT NULL DEFAULT false,
            churn_risk_flag         boolean NOT NULL DEFAULT false,
            reached_target_flag     boolean NOT NULL DEFAULT false,

            first_seen_at           timestamptz NULL,
            first_trip_at           timestamptz NULL,
            last_trip_at            timestamptz NULL,
            last_supply_at          timestamptz NULL,
            last_calculated_at      timestamptz NOT NULL DEFAULT now(),

            source                  text NOT NULL DEFAULT 'driver_state_snapshot',

            PRIMARY KEY (snapshot_date, driver_profile_id)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dss_lifecycle
            ON growth.yango_lima_driver_state_snapshot (lifecycle_state);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dss_performance
            ON growth.yango_lima_driver_state_snapshot (performance_state);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dss_retention
            ON growth.yango_lima_driver_state_snapshot (retention_state);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dss_weekly_target
            ON growth.yango_lima_driver_state_snapshot (weekly_trips_target);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dss_distance_target
            ON growth.yango_lima_driver_state_snapshot (distance_to_weekly_target);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dss_recoverable
            ON growth.yango_lima_driver_state_snapshot (recoverable_flag);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dss_churn_risk
            ON growth.yango_lima_driver_state_snapshot (churn_risk_flag);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dss_reached_target
            ON growth.yango_lima_driver_state_snapshot (reached_target_flag);
    """)

    # ── Table 2: Program Eligibility Daily ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_program_eligibility_daily (
            eligibility_date        date NOT NULL,
            driver_profile_id       text NOT NULL,
            program_code            text NOT NULL,

            eligible_flag           boolean NOT NULL,
            eligibility_reason      text NULL,
            priority                integer NULL,

            lifecycle_state         text NULL,
            performance_state       text NULL,
            retention_state         text NULL,
            distance_to_weekly_target integer NULL,

            created_at              timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (eligibility_date, driver_profile_id, program_code)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ped_program
            ON growth.yango_lima_program_eligibility_daily (program_code);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ped_eligible
            ON growth.yango_lima_program_eligibility_daily (eligible_flag);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ped_date_program
            ON growth.yango_lima_program_eligibility_daily (eligibility_date, program_code);
    """)

    # ── Table 3: Daily Opportunity List ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_daily_opportunity_list (
            opportunity_date        date NOT NULL,
            driver_profile_id       text NOT NULL,
            opportunity_type        text NOT NULL,
            program_code            text NOT NULL,

            priority                integer NULL,
            opportunity_reason      text NULL,

            lifecycle_state         text NULL,
            performance_state       text NULL,
            retention_state         text NULL,

            completed_orders_week   integer NULL,
            supply_hours_week       numeric(18,4) NULL,
            distance_to_weekly_target integer NULL,
            trips_per_supply_hour_week numeric(18,4) NULL,

            management_status       text NOT NULL DEFAULT 'PENDING_ACTION',
            assigned_agent          text NULL,
            action_id               uuid NULL,

            generated_at            timestamptz NOT NULL DEFAULT now(),
            closed_at               timestamptz NULL,

            PRIMARY KEY (opportunity_date, driver_profile_id, opportunity_type)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dol_type
            ON growth.yango_lima_daily_opportunity_list (opportunity_type);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dol_program
            ON growth.yango_lima_daily_opportunity_list (program_code);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dol_status
            ON growth.yango_lima_daily_opportunity_list (management_status);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dol_agent
            ON growth.yango_lima_daily_opportunity_list (assigned_agent);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_daily_opportunity_list;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_program_eligibility_daily;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_driver_state_snapshot;")
