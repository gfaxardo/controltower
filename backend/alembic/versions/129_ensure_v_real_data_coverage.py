"""
Garantiza ops.v_real_data_coverage alineada con la cadena canónica hourly-first.

Misma semántica que 101_real_rollup_from_day_v2 (agregado por país desde rollup diario).
Usa ops.real_rollup_day_fact directamente para que la vista exista aunque falte
ops.mv_real_rollup_day (compatibilidad con despliegues parciales).

Revision ID: 129_ensure_v_real_data_coverage
Revises: 128_omniview_matrix_issue_action_log
"""

from alembic import op

revision = "129_ensure_v_real_data_coverage"
down_revision = "128_omniview_matrix_issue_action_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW ops.v_real_data_coverage AS
        SELECT
            country,
            MIN(trip_day) AS min_trip_date,
            MAX(trip_day) AS last_trip_date,
            MAX(last_trip_ts) AS last_trip_ts,
            date_trunc('month', MIN(trip_day))::date AS min_month,
            date_trunc('week', MIN(trip_day))::date AS min_week,
            date_trunc('month', MAX(trip_day))::date AS last_month_with_data,
            date_trunc('week', MAX(trip_day))::date AS last_week_with_data
        FROM ops.real_rollup_day_fact
        WHERE country IN ('pe', 'co')
        GROUP BY country
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
