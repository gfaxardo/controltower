"""
CT-REAL-DIMENSION-GOVERNANCE: Dimensiones canónicas REAL.

Crea canon.dim_lob_group, canon.dim_lob, canon.dim_service_type como única fuente
de verdad para service types y LOB. Refactoriza v_real_trips_service_lob_resolved
y v_real_trips_with_lob_v2 para usar dimensiones; mantiene contrato API
(real_tipo_servicio_norm = service_type_key, lob_group = lob_group_label).
"""
from alembic import op

revision = "090_real_dimension_governance"
down_revision = "080_real_lob_canonical_service_type_unified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1) canon.dim_lob_group ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS canon.dim_lob_group (
            lob_group_key TEXT PRIMARY KEY,
            lob_group_label TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true
        )
    """)
    op.execute("COMMENT ON TABLE canon.dim_lob_group IS 'Gobernanza REAL: grupos LOB canónicos. Fuente de labels para API.'")
    op.execute("""
        INSERT INTO canon.dim_lob_group (lob_group_key, lob_group_label, is_active) VALUES
        ('auto_taxi', 'auto taxi', true),
        ('tuk_tuk', 'tuk tuk', true),
        ('delivery', 'delivery', true),
        ('taxi_moto', 'taxi moto', true),
        ('other', 'Other', true)
        ON CONFLICT (lob_group_key) DO UPDATE SET lob_group_label = EXCLUDED.lob_group_label
    """)

    # --- 2) canon.dim_lob_real (nombre distinto a canon.dim_lob de 041 que usa lob_id) ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS canon.dim_lob_real (
            lob_key TEXT PRIMARY KEY,
            lob_label TEXT NOT NULL,
            lob_group_key TEXT NOT NULL REFERENCES canon.dim_lob_group(lob_group_key),
            is_active BOOLEAN NOT NULL DEFAULT true
        )
    """)
    op.execute("COMMENT ON TABLE canon.dim_lob_real IS 'Gobernanza REAL: LOB por grupo. 1:1 con grupo en semilla.'")
    op.execute("""
        INSERT INTO canon.dim_lob_real (lob_key, lob_label, lob_group_key, is_active) VALUES
        ('auto_taxi', 'auto taxi', 'auto_taxi', true),
        ('tuk_tuk', 'tuk tuk', 'tuk_tuk', true),
        ('delivery', 'delivery', 'delivery', true),
        ('taxi_moto', 'taxi moto', 'taxi_moto', true),
        ('other', 'Other', 'other', true)
        ON CONFLICT (lob_key) DO UPDATE SET lob_label = EXCLUDED.lob_label, lob_group_key = EXCLUDED.lob_group_key
    """)

    # --- 3) canon.dim_service_type ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS canon.dim_service_type (
            service_type_key TEXT PRIMARY KEY,
            service_type_label TEXT NOT NULL,
            lob_key TEXT NOT NULL REFERENCES canon.dim_lob_real(lob_key),
            lob_group_key TEXT NOT NULL REFERENCES canon.dim_lob_group(lob_group_key),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("COMMENT ON TABLE canon.dim_service_type IS 'Gobernanza REAL: tipo de servicio canónico. Lookup por canon.normalize_real_tipo_servicio().'")
    op.execute("""
        INSERT INTO canon.dim_service_type (service_type_key, service_type_label, lob_key, lob_group_key, is_active) VALUES
        ('economico', 'Económico', 'auto_taxi', 'auto_taxi', true),
        ('comfort', 'Comfort', 'auto_taxi', 'auto_taxi', true),
        ('comfort_plus', 'Comfort Plus', 'auto_taxi', 'auto_taxi', true),
        ('tuk_tuk', 'Tuk Tuk', 'tuk_tuk', 'tuk_tuk', true),
        ('minivan', 'Minivan', 'auto_taxi', 'auto_taxi', true),
        ('premier', 'Premier', 'auto_taxi', 'auto_taxi', true),
        ('standard', 'Standard', 'auto_taxi', 'auto_taxi', true),
        ('start', 'Start', 'auto_taxi', 'auto_taxi', true),
        ('xl', 'XL', 'auto_taxi', 'auto_taxi', true),
        ('economy', 'Economy', 'auto_taxi', 'auto_taxi', true),
        ('delivery', 'Delivery', 'delivery', 'delivery', true),
        ('cargo', 'Cargo', 'delivery', 'delivery', true),
        ('moto', 'Moto', 'taxi_moto', 'taxi_moto', true),
        ('taxi_moto', 'Taxi Moto', 'taxi_moto', 'taxi_moto', true)
        ON CONFLICT (service_type_key) DO UPDATE SET
            service_type_label = EXCLUDED.service_type_label,
            lob_key = EXCLUDED.lob_key,
            lob_group_key = EXCLUDED.lob_group_key
    """)

    # --- 4) Vista resuelta usando dimensiones (mantiene columnas tipo_servicio_norm, lob_group_resolved) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2 CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_trips_service_lob_resolved AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                t.pago_corporativo,
                t.distancia_km,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                park_id_raw,
                COALESCE(NULLIF(TRIM(park_name_raw::text), ''), NULLIF(TRIM(park_city_raw::text), ''), park_id_raw::text) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                revenue,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE
                    WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_key
        ),
        with_norm AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                revenue,
                canon.normalize_real_tipo_servicio(tipo_servicio::text) AS tipo_servicio_norm
            FROM with_country
        )
        SELECT
            r.country,
            r.city,
            r.park_id,
            r.park_name,
            r.fecha_inicio_viaje,
            r.tipo_servicio AS tipo_servicio_raw,
            r.tipo_servicio_norm,
            COALESCE(g.lob_group_label, 'UNCLASSIFIED') AS lob_group_resolved,
            (d.service_type_key IS NULL OR NOT d.is_active) AS is_unclassified,
            CASE WHEN r.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            r.revenue,
            r.comision_empresa_asociada,
            r.distancia_km
        FROM with_norm r
        LEFT JOIN canon.dim_service_type d ON d.service_type_key = r.tipo_servicio_norm AND d.is_active = true
        LEFT JOIN canon.dim_lob_group g ON g.lob_group_key = d.lob_group_key AND g.is_active = true
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_service_lob_resolved IS
        'Capa resuelta por viaje: tipo_servicio_raw -> service_type_key (canon.normalize_real_tipo_servicio) -> dimensiones canon.dim_service_type + canon.dim_lob_group. lob_group_resolved = label para contrato API.'
    """)

    # --- 5) v_real_trips_with_lob_v2: contrato sin cambios ---
    op.execute("""
        CREATE VIEW ops.v_real_trips_with_lob_v2 AS
        SELECT
            country,
            city,
            park_id,
            park_name,
            fecha_inicio_viaje,
            tipo_servicio_norm AS real_tipo_servicio_norm,
            lob_group_resolved AS lob_group,
            segment_tag,
            revenue,
            comision_empresa_asociada,
            distancia_km
        FROM ops.v_real_trips_service_lob_resolved
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_with_lob_v2 IS
        'Real LOB v2: wrapper sobre v_real_trips_service_lob_resolved. Contrato: real_tipo_servicio_norm (service_type_key), lob_group (label).'
    """)

    # --- 6) Sincronizar dim_real_service_type_lob desde dim_service_type (compatibilidad scripts) ---
    op.execute("""
        INSERT INTO canon.dim_real_service_type_lob (service_type_norm, lob_group, mapping_source, is_active, notes, updated_at)
        SELECT d.service_type_key, g.lob_group_label, 'dim_governance_090', true, d.service_type_label, now()
        FROM canon.dim_service_type d
        JOIN canon.dim_lob_group g ON g.lob_group_key = d.lob_group_key
        WHERE d.is_active AND g.is_active
        ON CONFLICT (service_type_norm) DO UPDATE SET
            lob_group = EXCLUDED.lob_group,
            mapping_source = EXCLUDED.mapping_source,
            updated_at = now()
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2 CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved CASCADE")
    # Restaurar vista desde dim_real_service_type_lob (070/080)
    op.execute("""
        CREATE VIEW ops.v_real_trips_service_lob_resolved AS
        WITH base AS (
            SELECT t.park_id, t.tipo_servicio, t.fecha_inicio_viaje, t.comision_empresa_asociada, t.pago_corporativo, t.distancia_km,
                p.id AS park_id_raw, p.name AS park_name_raw, p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100 AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT park_id, tipo_servicio, fecha_inicio_viaje, comision_empresa_asociada, pago_corporativo, distancia_km, park_id_raw,
                COALESCE(NULLIF(TRIM(park_name_raw::text), ''), NULLIF(TRIM(park_city_raw::text), ''), park_id_raw::text) AS park_name,
                CASE WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali' WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla' WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta' WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa' WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, ''))) END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT park_id, park_name, tipo_servicio, fecha_inicio_viaje, comision_empresa_asociada, pago_corporativo, distancia_km,
                GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(NULLIF(TRIM(city_norm), ''), ''), 'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT park_id, park_name, tipo_servicio, fecha_inicio_viaje, comision_empresa_asociada, pago_corporativo, distancia_km, revenue,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe' ELSE '' END AS country
            FROM with_key
        ),
        with_norm AS (
            SELECT country, city, park_id, park_name, tipo_servicio, fecha_inicio_viaje, comision_empresa_asociada, pago_corporativo, distancia_km, revenue,
                canon.normalize_real_tipo_servicio(tipo_servicio::text) AS tipo_servicio_norm
            FROM with_country
        )
        SELECT r.country, r.city, r.park_id, r.park_name, r.fecha_inicio_viaje,
            r.tipo_servicio AS tipo_servicio_raw,
            r.tipo_servicio_norm,
            COALESCE(d.lob_group, 'UNCLASSIFIED') AS lob_group_resolved,
            (d.service_type_norm IS NULL OR NOT COALESCE(d.is_active, true)) AS is_unclassified,
            CASE WHEN r.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            r.revenue, r.comision_empresa_asociada, r.distancia_km
        FROM with_norm r
        LEFT JOIN canon.dim_real_service_type_lob d ON d.service_type_norm = r.tipo_servicio_norm AND d.is_active = true
    """)
    op.execute("""
        CREATE VIEW ops.v_real_trips_with_lob_v2 AS
        SELECT country, city, park_id, park_name, fecha_inicio_viaje,
            tipo_servicio_norm AS real_tipo_servicio_norm,
            lob_group_resolved AS lob_group,
            segment_tag, revenue, comision_empresa_asociada, distancia_km
        FROM ops.v_real_trips_service_lob_resolved
    """)
    op.execute("DROP TABLE IF EXISTS canon.dim_service_type CASCADE")
    op.execute("DROP TABLE IF EXISTS canon.dim_lob_real CASCADE")
    op.execute("DROP TABLE IF EXISTS canon.dim_lob_group CASCADE")