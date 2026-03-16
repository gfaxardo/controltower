"""
Recrear ops.mv_real_drill_dim_agg para que exponga la columna cancelled_trips (añadida en 103).
En PostgreSQL una vista creada con SELECT * fija la lista de columnas en la creación; al añadir
cancelled_trips a real_drill_dim_fact la vista no la exponía hasta recrearla.
"""
from alembic import op

revision = "105_recreate_mv_real_drill_dim_agg_cancelled"
down_revision = "104_real_margin_quality_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.mv_real_drill_dim_agg CASCADE")
    op.execute("CREATE VIEW ops.mv_real_drill_dim_agg AS SELECT * FROM ops.real_drill_dim_fact")
    op.execute("COMMENT ON VIEW ops.mv_real_drill_dim_agg IS 'Compatibilidad drill PRO: todas las columnas de real_drill_dim_fact (incl. cancelled_trips desde 103).'")
    op.execute("CREATE VIEW ops.v_real_drill_lob AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'lob'")
    op.execute("CREATE VIEW ops.v_real_drill_park AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'park'")
    op.execute("CREATE VIEW ops.v_real_drill_service_type AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'service_type'")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_service_type CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_drill_dim_agg CASCADE")
    op.execute("CREATE VIEW ops.mv_real_drill_dim_agg AS SELECT * FROM ops.real_drill_dim_fact")
    op.execute("CREATE VIEW ops.v_real_drill_lob AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'lob'")
    op.execute("CREATE VIEW ops.v_real_drill_park AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'park'")
    op.execute("CREATE VIEW ops.v_real_drill_service_type AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'service_type'")
