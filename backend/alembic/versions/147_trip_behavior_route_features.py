"""
147 — Trip Behavior Route Features.

Fase 1F-5 — Agrega columnas de ruta a fraud.trip_risk_features
para soportar el motor de fraude conductual basado en viajes.

Columnas nuevas:
  - route_text: texto original de direccion (origen -> destino)
  - origin_cluster_key: clave de cluster de origen normalizada
  - destination_cluster_key: clave de cluster de destino normalizada
  - route_signature: firma de ruta origin_norm -> destination_norm
  - reverse_route_signature: firma de ruta inversa
  - route_parse_quality: ok / partial / failed
  - behavior_window: ventana de analisis (D-1, D-7, D-30)

Indices nuevos:
  - origin_cluster_key
  - route_signature
  - driver_id + origin_cluster_key
  - driver_id + route_signature
  - park_id + origin_cluster_key
  - computed_at (si no existe)

No rompe datos existentes (columnas NULL por defecto).
"""
from alembic import op

revision = "147_trip_behavior_route_features"
down_revision = "146_routine_run_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agregar columnas de ruta
    for col_sql in [
        "ALTER TABLE fraud.trip_risk_features ADD COLUMN IF NOT EXISTS route_text TEXT",
        "ALTER TABLE fraud.trip_risk_features ADD COLUMN IF NOT EXISTS origin_cluster_key TEXT",
        "ALTER TABLE fraud.trip_risk_features ADD COLUMN IF NOT EXISTS destination_cluster_key TEXT",
        "ALTER TABLE fraud.trip_risk_features ADD COLUMN IF NOT EXISTS route_signature TEXT",
        "ALTER TABLE fraud.trip_risk_features ADD COLUMN IF NOT EXISTS reverse_route_signature TEXT",
        "ALTER TABLE fraud.trip_risk_features ADD COLUMN IF NOT EXISTS route_parse_quality TEXT",
        "ALTER TABLE fraud.trip_risk_features ADD COLUMN IF NOT EXISTS behavior_window TEXT",
        "ALTER TABLE fraud.trip_risk_features ADD COLUMN IF NOT EXISTS duration_seconds NUMERIC",
    ]:
        op.execute(col_sql)

    # Indices
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_origin_cluster ON fraud.trip_risk_features(origin_cluster_key)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_route_sig ON fraud.trip_risk_features(route_signature)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_driver_origin ON fraud.trip_risk_features(driver_id, origin_cluster_key)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_driver_route ON fraud.trip_risk_features(driver_id, route_signature)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_park_origin ON fraud.trip_risk_features(park_id, origin_cluster_key)",
    ]:
        op.execute(idx_sql)


def downgrade() -> None:
    for col in [
        "behavior_window", "route_parse_quality", "reverse_route_signature",
        "route_signature", "destination_cluster_key", "origin_cluster_key",
        "route_text", "duration_seconds",
    ]:
        op.execute(f"ALTER TABLE fraud.trip_risk_features DROP COLUMN IF EXISTS {col}")
