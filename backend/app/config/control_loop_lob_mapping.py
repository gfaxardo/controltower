"""
Mapeo auditable: etiquetas Excel de proyección agregada → clave canónica interna (snake_case).

El **real** comparable con Omniview se resuelve después a `business_slice_name` vía
`ops.business_slice_mapping_rules` + `ops.control_loop_plan_line_to_business_slice`
(ver control_loop_business_slice_resolve).
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

_EXCEL_ALIASES: Dict[str, str] = {
    "auto regular": "auto_taxi",
    "auto_regular": "auto_taxi",
    "autoregular": "auto_taxi",
    "auto taxi": "auto_taxi",
    "tuk tuk": "tuk_tuk",
    "tuk-tuk": "tuk_tuk",
    "tuktuk": "tuk_tuk",
    "delivery": "delivery",
    "carga": "carga",
    "cargo": "carga",
    "moto": "taxi_moto",
    "taxi moto": "taxi_moto",
    "taxi_moto": "taxi_moto",
    "pro": "pro",
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
    return dict(_EXCEL_ALIASES)
