"""
CT-REAL-LOB-CANONICALIZATION: Unificación canónica de tipo_servicio REAL.

Objetivo: Eliminar duplicidad/fragmentación en vistas REAL (confort+/confort plus,
tuk_tuk/tuk-tuk, express/mensajería) colapsando a claves canónicas únicas.

Cambios:
1. canon.normalize_real_tipo_servicio(raw): normalización robusta (unaccent, +->_plus,
   espacios/guiones->_) y mapeo a clave canónica única. Todas las variantes equivalentes
   devuelven la misma clave.
2. canon.dim_real_service_type_lob: upsert del catálogo canónico (comfort_plus, tuk_tuk,
   delivery, etc.) y lob_group consistente. Mantenemos compatibilidad con filas existentes.
3. canon.map_real_tipo_servicio_to_lob_group: sincronizar desde dim (opcional, legacy).

Criterio: canonical_key estable (snake_case); display_label puede añadirse en API si se desea.
"""
from alembic import op

revision = "080_real_lob_canonical_service_type_unified"
down_revision = "079_driver_segment_migrations_weekly_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1) Función canónica unificada: normalizar igual que ops (unaccent, +->_plus, espacios/guiones->_) luego mapear a clave única ---
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    op.execute(r"""
        CREATE OR REPLACE FUNCTION canon.normalize_real_tipo_servicio(raw text)
        RETURNS text
        LANGUAGE sql
        STABLE
        AS $$
        WITH normalized AS (
            SELECT regexp_replace(
                regexp_replace(
                    regexp_replace(
                        LOWER(TRIM(unaccent(COALESCE(raw, '')))),
                        '[+]', '_plus', 'g'
                    ),
                    '[\s\-]+', '_', 'g'
                ),
                '[^a-z0-9_]', '', 'g'
            ) AS key
        ),
        with_express AS (
            SELECT CASE WHEN key = 'expres' THEN 'express' ELSE key END AS key FROM normalized
        )
        SELECT CASE
            WHEN raw IS NULL OR TRIM(COALESCE(raw, '')) = '' THEN NULL
            WHEN LENGTH(TRIM(COALESCE(raw, ''))) > 30 THEN 'UNCLASSIFIED'
            WHEN (SELECT key FROM with_express) IN ('economico') THEN 'economico'
            WHEN (SELECT key FROM with_express) IN ('confort', 'comfort') THEN 'comfort'
            WHEN (SELECT key FROM with_express) IN ('confort_plus', 'comfort_plus') THEN 'comfort_plus'
            WHEN (SELECT key FROM with_express) IN ('tuk_tuk', 'tuktuk') THEN 'tuk_tuk'
            WHEN (SELECT key FROM with_express) IN ('minivan', 'premier', 'standard', 'start', 'xl', 'economy') THEN (SELECT key FROM with_express)
            WHEN (SELECT key FROM with_express) IN ('express', 'mensajeria', 'envios') THEN 'delivery'
            WHEN (SELECT key FROM with_express) IN ('cargo', 'moto', 'taxi_moto') THEN (SELECT key FROM with_express)
            ELSE (SELECT key FROM with_express)
        END
        $$
    """)
    op.execute("COMMENT ON FUNCTION canon.normalize_real_tipo_servicio(text) IS 'CT-REAL-LOB: normalización canónica unificada. Variantes (confort+/plus, tuk_tuk/tuk-tuk, express/mensajería) colapsan a una clave única.'")

    # --- 2) Catálogo canónico en dim_real_service_type_lob (upsert) ---
    op.execute("""
        INSERT INTO canon.dim_real_service_type_lob (service_type_norm, lob_group, mapping_source, is_active, notes, updated_at) VALUES
        ('economico', 'auto taxi', 'canonical_080', true, 'Económico', now()),
        ('comfort', 'auto taxi', 'canonical_080', true, 'Confort/Comfort', now()),
        ('comfort_plus', 'auto taxi', 'canonical_080', true, 'Confort+/Confort Plus/Comfort+', now()),
        ('tuk_tuk', 'tuk tuk', 'canonical_080', true, 'Tuk-tuk/tuk_tuk', now()),
        ('minivan', 'auto taxi', 'canonical_080', true, NULL, now()),
        ('premier', 'auto taxi', 'canonical_080', true, NULL, now()),
        ('standard', 'auto taxi', 'canonical_080', true, NULL, now()),
        ('start', 'auto taxi', 'canonical_080', true, NULL, now()),
        ('xl', 'auto taxi', 'canonical_080', true, NULL, now()),
        ('economy', 'auto taxi', 'canonical_080', true, NULL, now()),
        ('delivery', 'delivery', 'canonical_080', true, 'Express/Mensajería/Mensajeria/Envíos', now()),
        ('cargo', 'delivery', 'canonical_080', true, NULL, now()),
        ('moto', 'taxi moto', 'canonical_080', true, NULL, now()),
        ('taxi_moto', 'taxi moto', 'canonical_080', true, NULL, now())
        ON CONFLICT (service_type_norm) DO UPDATE SET
            lob_group = EXCLUDED.lob_group,
            mapping_source = EXCLUDED.mapping_source,
            notes = EXCLUDED.notes,
            updated_at = now()
    """)

    # --- 3) Sincronizar map legacy desde dim (opcional, para scripts que aún lean map) ---
    op.execute("""
        INSERT INTO canon.map_real_tipo_servicio_to_lob_group (real_tipo_servicio, lob_group)
        SELECT service_type_norm, lob_group
        FROM canon.dim_real_service_type_lob
        WHERE is_active = true
        ON CONFLICT (real_tipo_servicio) DO UPDATE SET lob_group = EXCLUDED.lob_group
    """)

    # --- 4) Desactivar claves antiguas que fueron reemplazadas por canónicas (evitar doble conteo) ---
    op.execute("""
        UPDATE canon.dim_real_service_type_lob
        SET is_active = false, notes = COALESCE(notes,'') || '; reemplazado por canonical_080'
        WHERE service_type_norm IN ('confort', 'confort+', 'tuk-tuk', 'mensajería', 'express', 'expres', 'envios')
          AND (mapping_source IS NULL OR mapping_source != 'canonical_080')
    """)


def downgrade() -> None:
    # Restaurar función a la definición de 070 (CASE explícito sin unaccent)
    op.execute("""
        CREATE OR REPLACE FUNCTION canon.normalize_real_tipo_servicio(raw text)
        RETURNS text
        LANGUAGE sql
        STABLE
        AS $$
            SELECT CASE
                WHEN raw IS NULL OR TRIM(raw::text) = '' THEN NULL
                WHEN LENGTH(TRIM(raw::text)) > 30 THEN 'UNCLASSIFIED'
                WHEN LOWER(TRIM(raw::text)) IN ('economico', 'económico') THEN 'economico'
                WHEN LOWER(TRIM(raw::text)) IN ('confort', 'comfort') THEN 'confort'
                WHEN LOWER(TRIM(raw::text)) = 'confort+' THEN 'confort+'
                WHEN LOWER(TRIM(raw::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                WHEN LOWER(TRIM(raw::text)) IN ('exprés','exprs') THEN 'express'
                WHEN LOWER(TRIM(raw::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(raw::text))
                WHEN LOWER(TRIM(raw::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                ELSE LOWER(TRIM(raw::text))
            END
        $$
    """)
    # Reactivar filas desactivadas
    op.execute("""
        UPDATE canon.dim_real_service_type_lob
        SET is_active = true, notes = NULL
        WHERE notes LIKE '%%reemplazado por canonical_080%%'
    """)
    # Quitar solo las filas insertadas por canonical_080 (dejar las que ya existían con otros mapping_source)
    op.execute("""
        DELETE FROM canon.dim_real_service_type_lob WHERE mapping_source = 'canonical_080'
    """)
