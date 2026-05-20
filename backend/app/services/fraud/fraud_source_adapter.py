"""Fase 1F — Source Adapter.

Lee viajes desde la fuente canonica (public.trips_2026) y los normaliza
al contrato fraud_normalized_trip. No inventa campos: si falta, null.
"""
from datetime import datetime, timedelta
from app.db.connection import get_db
from app.services.fraud.fraud_source_discovery_service import get_canonical_trip_source
from app.services.fraud.fraud_route_parser import (
    parse_route_text, build_origin_cluster_key, build_destination_cluster_key,
    build_route_signature, build_reverse_route_signature, normalize_address_key,
)


def normalize_trip(row, source_info):
    """Normaliza una fila de trips_2026 al contrato fraud_normalized_trip."""
    conductor_id = row.get("conductor_id") or row.get("driver_id")
    trip_id = row.get("codigo_pedido") or row.get("id")
    condicion = (row.get("condicion") or "").strip() if row.get("condicion") else None
    tarjeta = float(row.get("tarjeta") or 0)
    efectivo = float(row.get("efectivo") or 0)

    payment_method = None
    if tarjeta > 0:
        payment_method = "card"
    elif efectivo > 0:
        payment_method = "cash"

    # Duration derivado de fecha_finalizacion - fecha_inicio_viaje
    duration_seconds = None
    start_dt = row.get("fecha_inicio_viaje")
    end_dt = row.get("fecha_finalizacion")
    # Parse string dates if needed (from test fixtures)
    if isinstance(start_dt, str):
        try:
            from datetime import datetime as dt
            start_dt = dt.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            start_dt = None
    if isinstance(end_dt, str):
        try:
            from datetime import datetime as dt
            end_dt = dt.strptime(end_dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            end_dt = None
    if start_dt and end_dt:
        try:
            diff = end_dt - start_dt
            duration_seconds = round(diff.total_seconds(), 1)
        except Exception:
            pass

    # Route parsing desde direccion
    route_text = row.get("direccion")
    route_info = parse_route_text(route_text)

    normalized = {
        "source_table": source_info["source_table"],
        "source_trip_id": str(trip_id) if trip_id else None,
        "driver_id": str(conductor_id) if conductor_id else None,
        "park_id": str(row.get("park_id")) if row.get("park_id") else None,
        "trip_datetime": start_dt,
        "trip_status": condicion,
        "is_completed": condicion == source_info.get("completed_value", "Completado"),
        "payment_method": payment_method,
        "amount": float(row.get("precio_yango_pro")) if row.get("precio_yango_pro") else None,
        "distance": float(row.get("distancia_km")) if row.get("distancia_km") else None,
        "duration": duration_seconds,
        "duration_seconds": duration_seconds,
        "pickup_lat": None,
        "pickup_lng": None,
        "pickup_address": route_text,
        "pickup_cluster_key": normalize_address_key(route_text),
        "dropoff_lat": None,
        "dropoff_lng": None,
        "dropoff_address": None,
        "city": None,
        "country": None,
        "lob": row.get("tipo_servicio"),
        "segment": None,
        # ── Fase 1F-5: Route fields ──
        "route_text": route_text,
        "origin_text": route_info["origin_text"],
        "destination_text": route_info["destination_text"],
        "origin_norm": route_info["origin_norm"],
        "destination_norm": route_info["destination_norm"],
        "origin_cluster_key": None,  # Se rellena abajo
        "destination_cluster_key": None,  # Se rellena abajo
        "route_signature": route_info["route_signature"],
        "reverse_route_signature": route_info["reverse_route_signature"],
        "route_parse_quality": route_info["parse_quality"],
    }

    # Construir cluster keys usando el row enriquecido
    normalized["origin_cluster_key"] = build_origin_cluster_key(normalized)
    normalized["destination_cluster_key"] = build_destination_cluster_key(normalized)

    # Si route_signature no se genero via parser, intentar con cluster keys
    if not normalized["route_signature"]:
        normalized["route_signature"] = build_route_signature(normalized)
    if not normalized["reverse_route_signature"]:
        normalized["reverse_route_signature"] = build_reverse_route_signature(normalized)

    return normalized


def fetch_normalized_trips(date_from=None, date_to=None, driver_id=None, park_id=None, limit=5000):
    """Lee viajes normalizados desde public.trips_2026."""
    source_info = get_canonical_trip_source()
    table = source_info["source_table"]

    conditions = []
    params = {}

    if date_from:
        conditions.append(f"{source_info['date_column']} >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        conditions.append(f"{source_info['date_column']} < %(date_to)s")
        # date_to es exclusivo: sumamos 1 dia
        if isinstance(date_to, str):
            date_to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            params["date_to"] = date_to_dt + timedelta(days=1)
        else:
            params["date_to"] = date_to
    if driver_id:
        conditions.append(f"{source_info['driver_id_column']} = %(driver_id)s")
        params["driver_id"] = driver_id
    if park_id:
        conditions.append(f"{source_info['park_id_column']} = %(park_id)s")
        params["park_id"] = park_id

    # Solo completados
    conditions.append(f"{source_info['status_column']} = %(completed_value)s")
    params["completed_value"] = source_info["completed_value"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT conductor_id, codigo_pedido, id, park_id, fecha_inicio_viaje,
               fecha_finalizacion, condicion, precio_yango_pro, distancia_km,
               direccion, tipo_servicio, tarjeta, efectivo
        FROM {table}
        WHERE {where_clause}
        ORDER BY {source_info['date_column']} DESC
        LIMIT {int(limit)}
    """

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()

    normalized = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        normalized.append(normalize_trip(row_dict, source_info))

    return normalized


def get_bank_identity_rows(source="auto"):
    """Obtiene identidades bancarias de fuentes multiples.
    source: auto | public_payment_details | fraud_payment_identity_source | all
    NUNCA devuelve account_number completo. Solo account_hash + masked.
    """
    from app.services.fraud.fraud_feature_service import normalize_bank_account, mask_account_number, hash_bank_cluster_key

    results = []
    use_public = False
    use_fraud = False

    with get_db() as conn:
        cur = conn.cursor()

        # Determinar fuentes disponibles
        if source in ("auto", "all", "public_payment_details"):
            cur.execute("SELECT COUNT(*) FROM public.payment_details WHERE driver_id IS NOT NULL AND TRIM(driver_id) <> '' AND account_number IS NOT NULL AND TRIM(account_number) <> ''")
            pd_count = cur.fetchone()[0]
            use_public = pd_count > 0

        if source in ("auto", "all", "fraud_payment_identity_source"):
            cur.execute("SELECT COUNT(*) FROM fraud.payment_identity_source WHERE is_active = true")
            fis_count = cur.fetchone()[0]
            use_fraud = fis_count > 0

        # Prioridad auto: public.payment_details primero
        if use_public and source in ("auto", "all", "public_payment_details"):
            cur.execute("""
                SELECT driver_id, park_id, bank_name, account_number, account_type,
                       recipient_name, document_type, document_number
                FROM public.payment_details
                WHERE driver_id IS NOT NULL AND TRIM(driver_id) <> ''
                  AND account_number IS NOT NULL AND TRIM(account_number) <> ''
            """)
            for r in cur.fetchall():
                driver_id = str(r[0]).strip()
                bank_name = r[2]
                acct = r[3]
                bn_norm, _ = normalize_bank_account(bank_name, acct)
                results.append({
                    "driver_id": driver_id,
                    "park_id": str(r[1]) if r[1] else None,
                    "bank_name_norm": bn_norm,
                    "account_hash": hash_bank_cluster_key(bank_name, acct),
                    "masked_account_number": mask_account_number(acct),
                    "source_name": "public.payment_details",
                })

        if use_fraud and (source in ("all", "fraud_payment_identity_source") or (source == "auto" and not use_public)):
            cur.execute("""
                SELECT driver_id, park_id, bank_name_norm, account_hash,
                       masked_account_number, source_name
                FROM fraud.payment_identity_source
                WHERE is_active = true
            """)
            for r in cur.fetchall():
                results.append({
                    "driver_id": str(r[0]).strip(),
                    "park_id": str(r[1]) if r[1] else None,
                    "bank_name_norm": r[2],
                    "account_hash": r[3],
                    "masked_account_number": r[4],
                    "source_name": r[5],
                })

        cur.close()

    return results, {
        "source_mode": source,
        "public_payment_details_used": use_public,
        "fraud_payment_identity_used": use_fraud,
        "total_rows": len(results),
    }


def get_driver_bank_info(driver_id=None, park_id=None):
    """Wrapper legacy que usa get_bank_identity_rows con filtro."""
    rows, _ = get_bank_identity_rows(source="all")
    filtered = []
    for r in rows:
        if driver_id and r["driver_id"] != driver_id:
            continue
        if park_id and r.get("park_id") != park_id:
            continue
        filtered.append(r)
    return filtered
