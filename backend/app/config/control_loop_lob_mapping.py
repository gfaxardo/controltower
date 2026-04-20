"""
Mapeo auditable: etiquetas Excel de proyección agregada → clave canónica interna (snake_case).

El **real** comparable con Omniview se resuelve después a `business_slice_name` vía
`ops.business_slice_mapping_rules` + `ops.control_loop_plan_line_to_business_slice`
(ver control_loop_business_slice_resolve).

MANTENIMIENTO:
  - Agregar aliases aquí cuando aparezcan nuevas variantes de nombre en los archivos de plan.
  - Cada alias es raw_name_lower → canonical_key.
  - Si el raw_name incluye subcategoría (ej. "delivery bicicleta"), mapear a la LOB base.
  - Las tildes se eliminan antes de la comparación (via remove_accents).
  - Versión: 2 — 2026-04-16 (agregados aliases de subtipos y typos conocidos)
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

# Claves canónicas internas (staging.control_loop_plan_metric_long.linea_negocio_canonica).
CANONICAL_LINE_KEYS = (
    "auto_taxi",
    "tuk_tuk",
    "delivery",
    "carga",
    "taxi_moto",
    "pro",
    "yma",
    "ymm",
)

# Candidatos de nombre de tajada (business_slice_name) a probar contra reglas activas por ciudad.
# Debe mantenerse alineado con la columna Tajada de 1_Config_Tajadas / negocio.
PLAN_LINE_TO_SLICE_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "auto_taxi": ("Auto regular", "Auto Regular", "AUTO REGULAR", "Autos regular"),
    "tuk_tuk": ("Tuk Tuk", "TUK TUK", "Tuk tuk", "tuk tuk"),
    "delivery": ("Delivery", "DELIVERY"),
    "carga": ("Carga", "Cargo", "CARGA"),
    "taxi_moto": ("Moto", "Taxi moto", "Taxi Moto", "TAXI MOTO"),
    "pro": ("PRO", "Pro"),
    "yma": ("YMA", "Yma"),
    "ymm": ("YMM", "Ymm"),
}

# ─── Alias map: raw_excel_name (lowercase, sin tildes) → canonical_key ────────
# Regla de normalización aplicada antes de buscar aquí:
#   remove_accents(raw.strip().lower()).replace("_", " ").split()→join(" ")
#
# Incluye:
#   - nombres exactos Excel estándar
#   - typos conocidos en archivos reales (ej. "dellivery" con doble l)
#   - subcategorías que mapean a la LOB base (ej. "delivery bicicleta" → "delivery")
#   - variantes regionales (ej. "mototaxi" → "taxi_moto")
_EXCEL_ALIASES: Dict[str, str] = {
    # ── Auto Taxi ──────────────────────────────────────────────────────────
    "auto regular": "auto_taxi",
    "auto_regular": "auto_taxi",
    "autoregular": "auto_taxi",
    "auto taxi": "auto_taxi",
    "auto": "auto_taxi",
    "autos": "auto_taxi",
    "autos regular": "auto_taxi",

    # ── Tuk Tuk ───────────────────────────────────────────────────────────
    "tuk tuk": "tuk_tuk",
    "tuk-tuk": "tuk_tuk",
    "tuktuk": "tuk_tuk",
    "tuk": "tuk_tuk",

    # ── Delivery / Mensajería ─────────────────────────────────────────────
    "delivery": "delivery",
    "deliveri": "delivery",          # typo fonotáctico
    "dellivery": "delivery",         # typo doble l (documentado en plan real)
    "deliveries": "delivery",
    "delivery bicicleta": "delivery",   # subtipo bici → LOB base
    "delivery bici": "delivery",
    "delivery moto": "delivery",        # subtipo moto → LOB base
    "delivery auto": "delivery",        # subtipo auto → LOB base
    "dellivery bicicleta": "delivery",  # typo + subtipo (Bogotá real)
    "dellivery bici": "delivery",
    "mensajeria": "delivery",
    "mensajería": "delivery",
    "mensajero": "delivery",
    "paqueteria": "delivery",
    "paquetería": "delivery",
    "express": "delivery",
    "envios": "delivery",
    "envíos": "delivery",

    # ── Carga ─────────────────────────────────────────────────────────────
    "carga": "carga",
    "cargo": "carga",
    "carga pesada": "carga",
    "carga ligera": "carga",
    "carga liviana": "carga",
    "transporte de carga": "carga",

    # ── Taxi Moto ─────────────────────────────────────────────────────────
    "moto": "taxi_moto",
    "taxi moto": "taxi_moto",
    "taxi_moto": "taxi_moto",
    "mototaxi": "taxi_moto",
    "moto taxi": "taxi_moto",
    "motocicleta": "taxi_moto",

    # ── PRO ───────────────────────────────────────────────────────────────
    "pro": "pro",
    "yego pro": "pro",
    "servicio pro": "pro",

    # ── YMA / YMM ─────────────────────────────────────────────────────────
    "yma": "yma",
    "ymm": "ymm",
}


def _normalize_excel_key(raw: str) -> str:
    from app.contracts.data_contract import remove_accents

    if not raw:
        return ""
    s = remove_accents(raw.strip().lower())
    s = s.replace("_", " ")
    s = " ".join(s.split())
    return s


def resolve_excel_line_to_canonical(raw_line: str) -> Tuple[Optional[str], str]:
    """Resuelve una etiqueta raw Excel → (canonical_key, normalized_key).

    Retorna (None, normalized_key) si no hay mapping conocido.
    canonical_key ∈ CANONICAL_LINE_KEYS o None.
    """
    key = _normalize_excel_key(raw_line)
    if not key:
        return None, ""
    if key in _EXCEL_ALIASES:
        return _EXCEL_ALIASES[key], key
    if key.replace(" ", "_") in CANONICAL_LINE_KEYS:
        return key.replace(" ", "_"), key
    if key in CANONICAL_LINE_KEYS:
        return key, key
    return None, key


def list_alias_map_for_audit() -> Dict[str, str]:
    """Devuelve copia del mapa de alias para auditoría."""
    return dict(_EXCEL_ALIASES)


def get_all_known_raw_lob_names() -> list[str]:
    """Lista todas las variantes raw conocidas, ordenadas."""
    return sorted(_EXCEL_ALIASES.keys())
