"""
133 — Fase 3.3.B: tabla ops.plan_lob_mapping (capa formal de normalización de PLAN).

Crea:
  ops.plan_lob_mapping
    Tabla auditable de alias LOB: raw_lob_name → canonical_lob_base.
    Permite centralizar mappings en DB, consultarlos y mantenerlos sin hardcode.
    La capa Python (control_loop_lob_mapping.py) sigue siendo la fuente primaria;
    esta tabla es el registro formal persistente para auditoría y futuras UI de configuración.

  ops.plan_resolution_log
    Registro de resoluciones ejecutadas por plan_version:
    raw_lob → canonical_lob → business_slice_name, con status y note.
    Se inserta en batch cuando se llama a GET /plan/mapping-audit o al cargar plan.

Motivo:
  Formalizar la capa de normalización de PLAN que actualmente vive
  sólo en código Python disperso, sin trazabilidad persistente.

down_revision: 132_control_loop_tajadas_realignment
"""

from alembic import op

revision = "133_plan_lob_mapping_audit"
down_revision = "132_control_loop_tajadas_realignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Tabla de alias LOB (catálogo central auditable) ────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.plan_lob_mapping (
            id                  SERIAL PRIMARY KEY,
            raw_lob_name        TEXT NOT NULL,
            canonical_lob_base  TEXT,
            raw_country         TEXT,
            raw_city            TEXT,
            status              TEXT NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'deprecated', 'unmapped')),
            notes               TEXT,
            source              TEXT NOT NULL DEFAULT 'code_alias_map',
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE ops.plan_lob_mapping IS
        'Catálogo formal de aliases LOB para normalización de planes.
         raw_lob_name (lower, sin tildes) → canonical_lob_base (snake_case).
         Fuente primaria: app/config/control_loop_lob_mapping.py.
         status=unmapped indica LOBs conocidos sin mapping posible.';
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_plan_lob_mapping_raw_geo
        ON ops.plan_lob_mapping (raw_lob_name, COALESCE(raw_country,''), COALESCE(raw_city,''))
        WHERE status = 'active'
        """
    )

    # ── 2. Poblar con aliases conocidos del código ────────────────────────
    # Aliases estándar sin contexto geo (aplican a cualquier país/ciudad)
    op.execute(
        """
        INSERT INTO ops.plan_lob_mapping (raw_lob_name, canonical_lob_base, status, notes, source)
        VALUES
          ('auto regular',          'auto_taxi', 'active', 'nombre estándar Excel',        'code_alias_map'),
          ('auto taxi',             'auto_taxi', 'active', 'variante display',              'code_alias_map'),
          ('auto',                  'auto_taxi', 'active', 'abreviatura',                   'code_alias_map'),
          ('autos regular',         'auto_taxi', 'active', 'plural',                        'code_alias_map'),
          ('tuk tuk',               'tuk_tuk',  'active', 'nombre estándar',               'code_alias_map'),
          ('tuktuk',                'tuk_tuk',  'active', 'sin espacio',                   'code_alias_map'),
          ('delivery',              'delivery', 'active', 'nombre estándar',               'code_alias_map'),
          ('dellivery',             'delivery', 'active', 'typo doble l — frecuente',      'code_alias_map'),
          ('delivery bicicleta',    'delivery', 'active', 'subtipo bici → LOB base',       'code_alias_map'),
          ('delivery bici',         'delivery', 'active', 'abreviatura subtipo bici',      'code_alias_map'),
          ('delivery moto',         'delivery', 'active', 'subtipo moto → LOB base',       'code_alias_map'),
          ('delivery auto',         'delivery', 'active', 'subtipo auto → LOB base',       'code_alias_map'),
          ('dellivery bicicleta',   'delivery', 'active', 'typo+subtipo — Bogotá real',    'code_alias_map'),
          ('dellivery bici',        'delivery', 'active', 'typo+abreviatura',              'code_alias_map'),
          ('mensajeria',            'delivery', 'active', 'variante regional',             'code_alias_map'),
          ('paqueteria',            'delivery', 'active', 'variante regional',             'code_alias_map'),
          ('envios',                'delivery', 'active', 'variante regional',             'code_alias_map'),
          ('carga',                 'carga',    'active', 'nombre estándar',               'code_alias_map'),
          ('cargo',                 'carga',    'active', 'variante inglés',               'code_alias_map'),
          ('carga pesada',          'carga',    'active', 'subtipo → LOB base',            'code_alias_map'),
          ('carga ligera',          'carga',    'active', 'subtipo → LOB base',            'code_alias_map'),
          ('moto',                  'taxi_moto','active', 'abreviatura',                   'code_alias_map'),
          ('taxi moto',             'taxi_moto','active', 'nombre estándar',               'code_alias_map'),
          ('mototaxi',              'taxi_moto','active', 'variante compuesta',            'code_alias_map'),
          ('pro',                   'pro',      'active', 'nombre estándar',               'code_alias_map'),
          ('yego pro',              'pro',      'active', 'variante con marca',            'code_alias_map'),
          ('yma',                   'yma',      'active', 'nombre estándar',               'code_alias_map'),
          ('ymm',                   'ymm',      'active', 'nombre estándar',               'code_alias_map')
        ON CONFLICT DO NOTHING
        """
    )

    # ── 3. Tabla de log de resoluciones por plan_version ─────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.plan_resolution_log (
            id                      SERIAL PRIMARY KEY,
            plan_version            TEXT NOT NULL,
            raw_country             TEXT,
            raw_city                TEXT,
            raw_lob                 TEXT,
            canonical_country       TEXT,
            canonical_city          TEXT,
            canonical_lob_base      TEXT,
            business_slice_name     TEXT,
            resolution_status       TEXT NOT NULL
                                        CHECK (resolution_status IN ('resolved','unresolved','ambiguous')),
            resolution_source       TEXT,
            resolution_note         TEXT,
            period                  TEXT,
            resolved_at             TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE ops.plan_resolution_log IS
        'Log de resoluciones raw_lob → business_slice_name por plan_version.
         Se inserta al consultar GET /plan/mapping-audit o al auditar un plan cargado.
         Permite ver historial de cobertura y evolución de mappings.';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_plan_resolution_log_version
        ON ops.plan_resolution_log (plan_version, resolution_status)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.plan_resolution_log")
    op.execute("DROP TABLE IF EXISTS ops.plan_lob_mapping")
