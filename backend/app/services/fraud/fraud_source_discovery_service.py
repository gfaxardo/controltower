"""Fase 1F — Source Discovery Service.

Inspecciona fuentes disponibles en PostgreSQL y devuelve metadatos
de tablas/columnas, identificando la fuente canonica candidata
y las capacidades disponibles.
"""
from app.db.connection import get_db


def discover_trip_sources():
    """Devuelve metadata de tablas de viajes disponibles."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
            AND (table_name ILIKE '%trip%' OR table_name ILIKE '%viaje%')
            ORDER BY table_schema, table_name
        """)
        tables = [{"schema": r[0], "table": r[1]} for r in cur.fetchall()]
        cur.close()
    return tables


def get_canonical_trip_source():
    """Devuelve la fuente canonica recomendada para viajes."""
    return {
        "source_table": "public.trips_2026",
        "driver_id_column": "conductor_id",
        "date_column": "fecha_inicio_viaje",
        "status_column": "condicion",
        "completed_value": "Completado",
        "trip_id_column": "codigo_pedido",
        "amount_column": "precio_yango_pro",
        "distance_column": "distancia_km",
        "pickup_address_column": "direccion",
        "park_id_column": "park_id",
        "lob_column": "tipo_servicio",
        "card_column": "tarjeta",
        "cash_column": "efectivo",
    }


def get_capabilities():
    """Devuelve las capacidades detectadas para el motor antifraude."""
    return {
        "has_payment_method": True,
        "payment_method_source": "derived: tarjeta > 0 => card, efectivo > 0 => cash",
        "has_amount": True,
        "amount_column": "precio_yango_pro",
        "has_distance": True,
        "distance_column": "distancia_km",
        "has_duration": False,
        "has_pickup_latlng": False,
        "has_pickup_address": True,
        "pickup_address_column": "direccion",
        "has_bonus_source": False,
        "bonus_source_note": "module_bonus_thresholds existe pero no tiene driver_id directo",
        "has_balance_source": False,
        "balance_source_note": "No se encontro tabla de saldo/PLAC",
        "has_bank_source": True,
        "bank_source_table": "public.payment_details",
        "bank_required_columns_available": True,
        "bank_source_columns": ["driver_id", "bank_name", "account_number", "account_type", "recipient_name"],
        "bank_source_row_count": 0,
        "bank_source_note": "Tabla existe con columnas minimas pero 0 filas. Wiring listo, clusters esperando datos.",
    }
