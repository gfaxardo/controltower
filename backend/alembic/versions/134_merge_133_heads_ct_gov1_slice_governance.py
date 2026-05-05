"""
134 — Merge heads 133_* + CT-GOV-1 gobierno de tajadas (datos, sin cambio de esquema).

- dim.dim_business_slice_mapping: literal Excel \"Dellivery bicicleta\" → Delivery
  (decisión negocio: bicicleta es Delivery; el typo ya se homologa en proyección/real vía capa canónica).
- ops.business_slice_mapping_rules: activar reglas YMM inactivas (YMM es LOB válida;
  el fact semanal sigue dependiendo de viajes que matcheen reglas + refresh del loader).

down_revision: merge de 133_business_slice_canonical_mapping_layer y 133_plan_lob_mapping_audit
"""

from alembic import op

revision = "134_merge_133_heads_ct_gov1_slice_governance"
down_revision = (
    "133_business_slice_canonical_mapping_layer",
    "133_plan_lob_mapping_audit",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO dim.dim_business_slice_mapping (raw_value, canonical_value)
        SELECT 'Dellivery bicicleta', 'Delivery'
        WHERE NOT EXISTS (
            SELECT 1
            FROM dim.dim_business_slice_mapping d
            WHERE lower(trim(d.raw_value)) = lower(trim('Dellivery bicicleta'))
        )
        """
    )
    op.execute(
        """
        UPDATE ops.business_slice_mapping_rules
        SET is_active = TRUE
        WHERE lower(trim(business_slice_name::text)) = 'ymm'
          AND is_active = FALSE
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM dim.dim_business_slice_mapping
        WHERE lower(trim(raw_value)) = lower(trim('Dellivery bicicleta'))
          AND lower(trim(canonical_value)) = lower(trim('Delivery'))
        """
    )
    # No revertimos is_active de YMM (riesgo de silenciar líneas operativas).
