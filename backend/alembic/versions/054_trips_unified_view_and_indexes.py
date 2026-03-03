"""
FASE 1 + FASE 2: VIEW public.trips_unified e índices mínimos.
- Si trips_all NO tiene 2026: VIEW = UNION ALL trips_all + trips_2026 (simple).
- Si trips_all SÍ tiene 2026: VIEW con corte por fecha para evitar duplicados.
  Implementación: corte por fecha (trips_all < 2026-01-01, trips_2026 >= 2026-01-01).
- Requiere que public.trips_2026 exista con las mismas columnas que trips_all.
  Si trips_2026 no existe, crear antes una tabla vacía con misma estructura.
- Índices CONCURRENTLY en ambas tablas (trip_ts/fecha_inicio_viaje, completados, park_id, driver_id).
"""
from alembic import op
from sqlalchemy import text

revision = "054_trips_unified_view"
down_revision = "053_real_lob_drill_pro"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Evitar timeout en servidor con statement_timeout bajo (CREATE VIEW puede tocar catálogos)
    op.execute("SET statement_timeout = '1h'")
    # Quitar vista previa si existe (evita UniqueViolation en pg_type por vista/registro huérfano)
    op.execute("DROP VIEW IF EXISTS public.trips_unified CASCADE")
    # FASE 1: VIEW unificada. Si trips_2026 existe: UNION con corte por fecha; si no: solo trips_all.
    conn = op.get_bind()
    r = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'trips_2026'
    """)).fetchone()
    if r:
        op.execute("""
            CREATE VIEW public.trips_unified AS
            SELECT * FROM public.trips_all
            WHERE fecha_inicio_viaje IS NULL OR fecha_inicio_viaje < '2026-01-01'::date
            UNION ALL
            SELECT * FROM public.trips_2026
            WHERE fecha_inicio_viaje >= '2026-01-01'::date
        """)
    else:
        op.execute("""
            CREATE VIEW public.trips_unified AS
            SELECT * FROM public.trips_all
        """)
    op.execute("""
        COMMENT ON VIEW public.trips_unified IS
        'Unión trips_all (histórico <2026) + trips_2026 (>=2026). Sin duplicados. Fuente para Driver Lifecycle y Real.'
    """)
    # FASE 2: Índices NO se crean aquí (trips_all/trips_2026 pueden ser enormes → statement timeout).
    # Crear manualmente con CONCURRENTLY y statement_timeout alto. Ver: backend/scripts/sql/trips_unified_indexes_concurrent.sql


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public.trips_unified CASCADE")
    # Índices: si se crearon con el script sql, borrarlos a mano si hace falta.
