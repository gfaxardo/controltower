"""Fase 1F-5 — Route Parser / Normalizador.

Parsea texto de ruta desde direccion (origen -> destino) y construye
claves de cluster para agrupacion de origenes, destinos y rutas.

Deterministico. Sin APIs externas. Sin geocodificacion.
"""
import re
from typing import Optional, Dict, Any


def normalize_text_address(value: Optional[str]) -> Optional[str]:
    """Normaliza direccion textual: lower, trim, remover dobles espacios, caracteres raros.

    No borra numeros importantes (calles, alturas).
    Devuelve None si el resultado es vacio.
    """
    if not value or not isinstance(value, str):
        return None

    text = value.strip().lower()
    if not text:
        return None

    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text)

    # Remover caracteres de control pero preservar letras, numeros, espacios, comas, puntos, guiones
    text = re.sub(r'[^\w\s,.\-áéíóúüñ]', '', text, flags=re.UNICODE)

    # Remover dobles comas/puntos
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'\.\s*\.', '.', text)

    text = text.strip()
    if len(text) < 2:
        return None

    return text


def parse_route_text(route_text: Optional[str]) -> Dict[str, Any]:
    """Parsea texto de ruta y extrae origen/destino.

    Soporta separadores: ->, →, - , a , hasta , |

    Returns:
        dict con origin_text, destination_text, origin_norm, destination_norm,
        route_signature, reverse_route_signature, parse_quality, separator_used
    """
    result = {
        "origin_text": None,
        "destination_text": None,
        "origin_norm": None,
        "destination_norm": None,
        "route_signature": None,
        "reverse_route_signature": None,
        "parse_quality": "failed",
        "separator_used": None,
    }

    if not route_text or not isinstance(route_text, str):
        return result

    text = route_text.strip()
    if not text:
        return result

    # Separadores en orden de prioridad
    separators = [
        ("->", True),
        ("\u2192", True),  # flecha unicode →
        (" - ", False),
        (" a ", False),
        (" hasta ", False),
        ("|", False),
    ]

    best_sep = None
    best_pos = -1

    for sep, _ in separators:
        pos = text.find(sep)
        if pos > 0:  # el separador debe estar en el medio, no al inicio
            if best_sep is None or pos < best_pos or (pos == best_pos and len(sep) > len(best_sep)):
                best_sep = sep
                best_pos = pos

    if best_sep is None:
        # Intentar split generico por patron "texto separador texto"
        # Si no se puede, devolver failed
        return result

    parts = text.split(best_sep, 1)
    if len(parts) != 2:
        return result

    origin_raw = parts[0].strip()
    destination_raw = parts[1].strip()

    if not origin_raw or not destination_raw:
        result["parse_quality"] = "partial"
        return result

    origin_norm = normalize_text_address(origin_raw)
    destination_norm = normalize_text_address(destination_raw)

    if not origin_norm or not destination_norm:
        result["parse_quality"] = "partial"
        if origin_norm:
            result["origin_text"] = origin_raw
            result["origin_norm"] = origin_norm
        if destination_norm:
            result["destination_text"] = destination_raw
            result["destination_norm"] = destination_norm
        return result

    route_sig = f"{origin_norm} -> {destination_norm}"
    reverse_route_sig = f"{destination_norm} -> {origin_norm}"

    result.update({
        "origin_text": origin_raw,
        "destination_text": destination_raw,
        "origin_norm": origin_norm,
        "destination_norm": destination_norm,
        "route_signature": route_sig,
        "reverse_route_signature": reverse_route_sig,
        "parse_quality": "ok",
        "separator_used": best_sep,
    })

    return result


def build_origin_cluster_key(row: Dict[str, Any]) -> Optional[str]:
    """Construye clave de cluster de origen.

    Prioridad:
    1. pickup_lat/lng rounded 5 decimales -> "lat,lng"
    2. origin_norm (de parsed route_text)
    3. pickup_address normalized
    4. null
    """
    lat = row.get("pickup_lat")
    lng = row.get("pickup_lng")
    if lat is not None and lng is not None:
        try:
            return f"{float(lat):.5f},{float(lng):.5f}"
        except (ValueError, TypeError):
            pass

    origin_norm = row.get("origin_norm")
    if origin_norm:
        return origin_norm[:200]

    pickup_addr = row.get("pickup_address_norm") or row.get("pickup_address")
    if pickup_addr:
        return normalize_text_address(pickup_addr)[:200] if normalize_text_address(pickup_addr) else None

    return None


def build_destination_cluster_key(row: Dict[str, Any]) -> Optional[str]:
    """Construye clave de cluster de destino.

    Prioridad:
    1. dropoff_lat/lng rounded 5 decimales
    2. destination_norm
    3. null (no tenemos dropoff_address)
    """
    lat = row.get("dropoff_lat")
    lng = row.get("dropoff_lng")
    if lat is not None and lng is not None:
        try:
            return f"{float(lat):.5f},{float(lng):.5f}"
        except (ValueError, TypeError):
            pass

    dest_norm = row.get("destination_norm")
    if dest_norm:
        return dest_norm[:200]

    return None


def build_route_signature(row: Dict[str, Any]) -> Optional[str]:
    """Construye firma de ruta origen->destino."""
    route_sig = row.get("route_signature")
    if route_sig:
        return route_sig

    origin = build_origin_cluster_key(row)
    dest = build_destination_cluster_key(row)
    if origin and dest:
        return f"{origin} -> {dest}"

    return None


def build_reverse_route_signature(row: Dict[str, Any]) -> Optional[str]:
    """Construye firma de ruta inversa destino->origen."""
    rev_sig = row.get("reverse_route_signature")
    if rev_sig:
        return rev_sig

    origin = build_origin_cluster_key(row)
    dest = build_destination_cluster_key(row)
    if origin and dest:
        return f"{dest} -> {origin}"

    return None


def normalize_address_key(address: Optional[str]) -> Optional[str]:
    """Genera clave de cluster simple a partir de direccion normalizada.

    Usado como fallback para pickup_cluster_key existente.
    """
    norm = normalize_text_address(address)
    if not norm:
        return None
    # Remover puntuacion para cluster key robusto
    key = re.sub(r'[^a-z0-9 ]', '', norm)
    key = re.sub(r'\s+', ' ', key).strip()
    if len(key) < 3:
        return None
    return key[:100]
