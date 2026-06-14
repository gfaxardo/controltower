"""
225 — LG-UNIVERSE-SIM-1G: Universe Config V2 + Simulation Tables

Creates 6 tables for universe configuration versioning and simulation.
Writers: simulation engine (future), config service (future).
Readers: simulation engine, worklist writer (future).

Additive only. No DROP.
down_revision: 224_lg_trace_1b_worklist_transition
"""
from alembic import op

revision = "225_lg_universe_sim_1g_config_tables"
down_revision = "224_lg_trace_1b_worklist_transition"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    # 1. config_version
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.universe_config_version (
            version_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            version_code            text UNIQUE NOT NULL,
            scope                   text NOT NULL DEFAULT 'lima',
            status                  text NOT NULL DEFAULT 'DRAFT'
                CHECK (status IN ('DRAFT','SIMULATED','APPROVED','ACTIVE','RETIRED')),
            effective_from          date,
            effective_to            date,
            created_by              text,
            approved_by             text,
            created_at              timestamptz NOT NULL DEFAULT now(),
            approved_at             timestamptz,
            notes                   text,
            source_contract_version text NOT NULL DEFAULT 'universe_config_v2'
        )
    """)

    # 2. definition_config
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.universe_definition_config (
            version_id                  uuid NOT NULL,
            universe_code               text NOT NULL,
            universe_label              text NOT NULL,
            universe_description        text,
            priority_order              integer NOT NULL,
            is_actionable               boolean NOT NULL,
            export_to_control_loop      boolean NOT NULL,
            recommended_channel         text,
            recommended_action_category text,
            target_metric               text,
            target_value                numeric,
            exit_condition_code         text,
            protected_condition_code    text,
            fallback_behavior           text,
            active_flag                 boolean NOT NULL DEFAULT true,
            PRIMARY KEY (version_id, universe_code)
        )
    """)

    # 3. rule_config
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.universe_rule_config (
            version_id      uuid NOT NULL,
            universe_code   text NOT NULL,
            rule_group      text NOT NULL,
            field_name      text NOT NULL,
            operator        text NOT NULL
                CHECK (operator IN ('=','!=','>','>=','<','<=','BETWEEN','IN','NOT_IN','IS_NULL','IS_NOT_NULL')),
            value           text,
            value_type      text NOT NULL,
            priority        integer NOT NULL,
            condition_logic text NOT NULL DEFAULT 'AND'
                CHECK (condition_logic IN ('AND','OR')),
            null_behavior   text NOT NULL DEFAULT 'FAIL'
                CHECK (null_behavior IN ('FAIL','PASS','IGNORE')),
            description     text,
            PRIMARY KEY (version_id, universe_code, rule_group, field_name, priority)
        )
    """)

    # 4. simulation_run
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.universe_simulation_run (
            simulation_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            version_id                  uuid NOT NULL,
            source_generated_date       date NOT NULL,
            run_at                      timestamptz NOT NULL DEFAULT now(),
            run_by                      text,
            status                      text NOT NULL DEFAULT 'RUNNING'
                CHECK (status IN ('RUNNING','COMPLETED','FAILED')),
            total_drivers               integer,
            exportable_drivers          integer,
            non_exportable_drivers      integer,
            changed_drivers             integer,
            diff_vs_current             jsonb,
            summary_json                jsonb,
            risk_flags_json             jsonb,
            notes                       text
        )
    """)

    # 5. simulation_result
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.universe_simulation_result (
            simulation_id                   uuid NOT NULL,
            driver_profile_id               text NOT NULL,
            current_universe                text,
            simulated_universe              text,
            changed_flag                    boolean NOT NULL,
            current_export_to_control_loop  boolean,
            simulated_export_to_control_loop boolean,
            reason_current                  text,
            reason_simulated                text,
            evidence_current                jsonb,
            evidence_simulated              jsonb,
            source_generated_date           date NOT NULL,
            created_at                      timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (simulation_id, driver_profile_id)
        )
    """)

    # 6. activation_audit
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.universe_config_activation_audit (
            activation_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            version_id              uuid NOT NULL,
            activated_at            timestamptz NOT NULL DEFAULT now(),
            activated_by            text,
            previous_version_id     uuid,
            rollback_version_id     uuid,
            summary_diff_json       jsonb,
            approval_notes          text
        )
    """)

    # Indexes
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_ucv_status ON growth.universe_config_version (status, scope)",
        "CREATE INDEX IF NOT EXISTS idx_udc_priority ON growth.universe_definition_config (version_id, priority_order)",
        "CREATE INDEX IF NOT EXISTS idx_urc_lookup ON growth.universe_rule_config (version_id, universe_code, priority)",
        "CREATE INDEX IF NOT EXISTS idx_usr_run ON growth.universe_simulation_run (version_id, source_generated_date, status)",
        "CREATE INDEX IF NOT EXISTS idx_usrr_changed ON growth.universe_simulation_result (simulation_id, changed_flag)",
        "CREATE INDEX IF NOT EXISTS idx_usrr_sim ON growth.universe_simulation_result (simulated_universe)",
        "CREATE INDEX IF NOT EXISTS idx_usrr_cur ON growth.universe_simulation_result (current_universe)",
    ]:
        op.execute(idx)

    # Seed DRAFT config V2
    from uuid import uuid4
    vid = str(uuid4())
    op.execute(f"INSERT INTO growth.universe_config_version (version_id, version_code, scope, status, notes) VALUES ('{vid}', 'UNIVERSE_V2_DRAFT_001', 'lima', 'DRAFT', 'Initial V2 draft from LG-UNIVERSE-CONFIG-1F') ON CONFLICT (version_code) DO NOTHING")

    # Use the inserted or existing version_id
    # Seed 10 universes
    universes = [
        (1, 'CEMETERY_LONG_CHURNED', 'Cemetery', False, False, 'Campaigns', 'DO_NOT_EXPORT', None, None),
        (2, 'RECOVERY_HIGH_VALUE', 'Recovery High', True, True, 'Agent', 'HIGH_VALUE_RECOVERY', 'reactivation', 1),
        (3, 'RECOVERY_LOW_VALUE', 'Recovery Low', True, True, 'SMS/WhatsApp', 'LOW_VALUE_RECOVERY', 'reactivation', 1),
        (4, 'NEW_0_14_TO_50', 'Nuevos', True, True, 'Agent/Call', 'ONBOARDING_PUSH', '50_trips_activation_window', 50),
        (5, 'REACTIVATED_TO_50', 'Reactivados', True, True, 'Agent/Call', 'ONBOARDING_PUSH', '50_trips_reactivation', 50),
        (6, 'RAMP_15_45_TO_100W', 'Ramp Up', True, True, 'Call/WhatsApp', 'PRODUCTIVITY_RAMP', '100_trips_weekly', 100),
        (7, 'CONSOLIDATION_46_90', 'Consolidation', True, True, 'Call/Follow-up', 'CONSOLIDATION_PUSH', '100_trips_weekly', 100),
        (8, 'ACTIVE_GROWTH_BAND_UP', 'Active Growth', True, True, 'WhatsApp/Call', 'BAND_GROWTH', 'band_up', None),
        (9, 'PROTECTED_TOP', 'Protected', False, False, 'Monitor', 'DO_NOT_EXPORT', None, None),
        (10, 'NO_DATA', 'No Data', False, False, None, 'DO_NOT_EXPORT', None, None),
    ]
    for p, code, label, act, exp, ch, cat, tgt, tval in universes:
        op.execute(f"INSERT INTO growth.universe_definition_config (version_id, universe_code, universe_label, priority_order, is_actionable, export_to_control_loop, recommended_channel, recommended_action_category, target_metric, target_value) SELECT version_id, '{code}', '{label}', {p}, {act}, {exp}, {ch or 'NULL'}, {cat or 'NULL'}, {tgt or 'NULL'}, {tval or 'NULL'} FROM growth.universe_config_version WHERE version_code='UNIVERSE_V2_DRAFT_001' ON CONFLICT (version_id, universe_code) DO NOTHING")

    # Seed rules
    rules = [
        ('CEMETERY_LONG_CHURNED', 'inactivity', 'inactivity_days', '>', '60', 'integer'),
        ('RECOVERY_HIGH_VALUE', 'inactivity_high', 'inactivity_days', 'BETWEEN', '7|60', 'integer'),
        ('RECOVERY_HIGH_VALUE', 'value_high', 'value_tier', '=', 'HIGH', 'text'),
        ('RECOVERY_LOW_VALUE', 'inactivity_low', 'inactivity_days', 'BETWEEN', '7|60', 'integer'),
        ('RECOVERY_LOW_VALUE', 'value_not_high', 'value_tier', '!=', 'HIGH', 'text'),
        ('NEW_0_14_TO_50', 'age', 'anchor_age_days', 'BETWEEN', '0|14', 'integer'),
        ('NEW_0_14_TO_50', 'trips_below', 'trips_since_anchor', '<', '50', 'integer'),
        ('NEW_0_14_TO_50', 'active', 'inactivity_days', '<', '7', 'integer'),
        ('REACTIVATED_TO_50', 'age', 'anchor_age_days', 'BETWEEN', '0|14', 'integer'),
        ('REACTIVATED_TO_50', 'trips_below', 'trips_since_anchor', '<', '50', 'integer'),
        ('REACTIVATED_TO_50', 'reactivated', 'has_reactivation_anchor', '=', 'true', 'boolean'),
        ('RAMP_15_45_TO_100W', 'age', 'anchor_age_days', 'BETWEEN', '15|45', 'integer'),
        ('RAMP_15_45_TO_100W', 'wk_below', 'weekly_trips', '<', '100', 'integer'),
        ('RAMP_15_45_TO_100W', 'active', 'inactivity_days', '<', '7', 'integer'),
        ('CONSOLIDATION_46_90', 'age', 'anchor_age_days', 'BETWEEN', '46|90', 'integer'),
        ('CONSOLIDATION_46_90', 'wk_below', 'weekly_trips', '<', '100', 'integer'),
        ('CONSOLIDATION_46_90', 'active', 'inactivity_days', '<', '7', 'integer'),
        ('ACTIVE_GROWTH_BAND_UP', 'age', 'anchor_age_days', '>', '90', 'integer'),
        ('ACTIVE_GROWTH_BAND_UP', 'wk_range', 'weekly_trips', 'BETWEEN', '1|99', 'integer'),
        ('ACTIVE_GROWTH_BAND_UP', 'active', 'inactivity_days', '<', '7', 'integer'),
        ('PROTECTED_TOP', 'wk_100', 'weekly_trips', '>=', '100', 'integer'),
        ('PROTECTED_TOP', 'new_goal', 'trips_since_anchor', '>=', '50', 'integer'),
    ]
    for uni, grp, fld, op, val, vtype in rules:
        op.execute(f"INSERT INTO growth.universe_rule_config (version_id, universe_code, rule_group, field_name, operator, value, value_type, priority) SELECT version_id, '{uni}', '{grp}', '{fld}', '{op}', '{val}', '{vtype}', 1 FROM growth.universe_config_version WHERE version_code='UNIVERSE_V2_DRAFT_001' ON CONFLICT (version_id, universe_code, rule_group, field_name, priority) DO NOTHING")


def downgrade():
    for tbl in [
        "growth.universe_simulation_result",
        "growth.universe_simulation_run",
        "growth.universe_rule_config",
        "growth.universe_definition_config",
        "growth.universe_config_activation_audit",
        "growth.universe_config_version",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl}")
