"""
Merge de las dos ramas: 012_plan_financials y 056_driver_lifecycle_pro_mvs.
No hace cambios en BD; solo unifica el historial para que 'alembic upgrade head' tenga un único head.
"""
from alembic import op

revision = "057_merge_plan_driver_lifecycle"
down_revision = ("012_plan_financials", "056_driver_lifecycle_pro_mvs")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
