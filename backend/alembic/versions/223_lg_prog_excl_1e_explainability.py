"""
223 — LG-PROG-EXCL-1E: Assignment Explainability Columns

Adds explainability fields to growth.yango_lima_exclusive_driver_worklist_daily:
- reason_text (human-readable explanation)
- evidence_json (JSONB with classification evidence)
- gap_to_target (integer)
- exit_condition (text)
- movement_hint (text)
- recommended_action_category (text)

Additive only. No DROP.
down_revision: 222_lg_prog_excl_1b_exclusive_worklist
"""

from alembic import op

revision = "223_lg_prog_excl_1e_explainability"
down_revision = "222_lg_prog_excl_1b_exclusive_worklist"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE growth.yango_lima_exclusive_driver_worklist_daily
        ADD COLUMN IF NOT EXISTS reason_text text
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_exclusive_driver_worklist_daily
        ADD COLUMN IF NOT EXISTS evidence_json jsonb
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_exclusive_driver_worklist_daily
        ADD COLUMN IF NOT EXISTS gap_to_target integer
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_exclusive_driver_worklist_daily
        ADD COLUMN IF NOT EXISTS exit_condition text
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_exclusive_driver_worklist_daily
        ADD COLUMN IF NOT EXISTS movement_hint text
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_exclusive_driver_worklist_daily
        ADD COLUMN IF NOT EXISTS recommended_action_category text
    """)


def downgrade():
    for col in ["reason_text", "evidence_json", "gap_to_target", "exit_condition", "movement_hint", "recommended_action_category"]:
        op.execute(f"ALTER TABLE growth.yango_lima_exclusive_driver_worklist_daily DROP COLUMN IF EXISTS {col}")
