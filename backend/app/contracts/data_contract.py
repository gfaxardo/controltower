from typing import Dict, Optional, List, Literal, Any
from dataclasses import dataclass
import logging
import unicodedata
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LEGACY — bi.real_monthly_agg
# ---------------------------------------------------------------------------
# Las siguientes funciones existían para resolver columnas de
# bi.real_monthly_agg (tabla legacy del pipeline BI externo).
# El sistema operativo actual de Control Tower NO usa bi.real_monthly_agg.
# Las fuentes canónicas son: trips_2025/2026, ops.*, dims canónicas.
# Se mantienen como stubs que retornan None para no romper imports legacy.
# ---------------------------------------------------------------------------

def get_revenue_column_name() -> Optional[str]:
    """LEGACY — bi.real_monthly_agg ya no es fuente operativa. Retorna None."""
    logger.debug("LEGACY_BI_SOURCE_DETECTED: get_revenue_column_name llamada — bi.real_monthly_agg no es source of truth operativo.")
    return None

def get_real_column_name(metric: str) -> Optional[str]:
    """LEGACY — resolver columna desde bi.real_monthly_agg. Ya no es fuente operativa."""
    logger.debug("LEGACY_BI_SOURCE_DETECTED: get_real_column_name('%s') — bi.real_monthly_agg no es source of truth operativo.", metric)
    if metric == 'trips':
        return 'orders_completed'
    return None

LINE_OF_BUSINESS_MAPPING = {
    'autos regular': 'Auto Taxi',
    'autos b2b': 'Auto Taxi',
    'autos regular b2b': 'Auto Taxi',
    'taxi': 'Auto Taxi',
    'auto taxi': 'Auto Taxi',
    'delivery': 'Delivery',
    'moto': 'Moto',
    'moto taxi': 'Moto',
}

TIPO_SERVICIO_MAPPING = {
    'económico': 'Auto Taxi',
    'economico': 'Auto Taxi',
    'confort': 'Auto Taxi',
    'confort+': 'Auto Taxi',
    'premier': 'Auto Taxi',
    'standard': 'Auto Taxi',
    'start': 'Auto Taxi',
    'minivan': 'Auto Taxi',
    'tuk-tuk': 'Auto Taxi',
    'mensajería': 'Delivery',
    'mensajeria': 'Delivery',
    'exprés': 'Delivery',
    'expres': 'Delivery',
    'cargo': 'Delivery',
    'envíos': 'Delivery',
    'envios': 'Delivery',
    'moto': 'Moto',
}

# --- REAL LOB: catálogo canónico (alineado con canon.normalize_real_tipo_servicio / 080) ---
# Claves internas en snake_case; display en UI puede usar REAL_SERVICE_TYPE_DISPLAY.
REAL_SERVICE_TYPES = (
    'economico',
    'comfort',
    'comfort_plus',
    'tuk_tuk',
    'delivery',
    'minivan',
    'premier',
    'standard',
    'start',
    'xl',
    'economy',
    'cargo',
    'moto',
    'taxi_moto',
    'UNCLASSIFIED',
)

# Mapeo canonical_key → etiqueta para UI (evita fragmentación confort+/CONFORT_PLUS en pantalla).
REAL_SERVICE_TYPE_DISPLAY: Dict[str, str] = {
    'comfort_plus': 'CONFORT_PLUS',
    'tuk_tuk': 'TUK_TUK',
    'delivery': 'DELIVERY',
    'economico': 'ECONOMY',
    'comfort': 'COMFORT',
    'minivan': 'MINIVAN',
    'premier': 'PREMIER',
    'standard': 'STANDARD',
    'start': 'START',
    'xl': 'XL',
    'economy': 'ECONOMY',
    'cargo': 'CARGO',
    'moto': 'MOTO',
    'taxi_moto': 'MOTO',
    'UNCLASSIFIED': 'UNCLASSIFIED',
}


def get_real_service_type_display(canonical_key: Optional[str]) -> str:
    """Devuelve la etiqueta de visualización para tipo de servicio REAL (ej. CONFORT_PLUS)."""
    if not canonical_key:
        return ''
    k = canonical_key.strip().lower()
    return REAL_SERVICE_TYPE_DISPLAY.get(k, canonical_key)


def normalize_line_of_business(plan_line: str) -> str:
    """
    Normaliza el nombre de línea de negocio del plan al formato usado en dim.dim_park.default_line_of_business.
    Retorna el nombre normalizado o el original si no hay mapeo.
    """
    if not plan_line:
        return plan_line
    
    plan_line_lower = plan_line.strip().lower()
    
    if plan_line_lower in LINE_OF_BUSINESS_MAPPING:
        return LINE_OF_BUSINESS_MAPPING[plan_line_lower]
    
    return plan_line

def get_all_universe_line_of_business() -> List[str]:
    """
    Obtiene todos los valores únicos de default_line_of_business del universo operativo.

    LEGACY: originalmente leía de bi.real_monthly_agg. Migrado a dim.dim_park directo
    dado que el sistema actual resuelve LOB desde dims canónicas + ops.*.
    """
    from app.db.connection import get_db
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT COALESCE(default_line_of_business, '') AS line_of_business
                FROM dim.dim_park
                WHERE COALESCE(default_line_of_business, '') != ''
                ORDER BY line_of_business
            """)
            results = cursor.fetchall()
            cursor.close()
            return [row[0] for row in results if row[0]]
    except Exception as e:
        logger.warning(f"Error al obtener líneas de negocio del universo: {e}")
        return []

def normalize_to_snake_case(value: str) -> str:
    """
    Convierte un valor a snake_case (espacios a underscore, lowercase).
    Ej: "Auto Taxi" → "auto_taxi"
    """
    if not value:
        return ''
    # Convertir a lowercase, reemplazar espacios con underscores
    normalized = value.strip().lower().replace(' ', '_')
    # Eliminar múltiples underscores consecutivos
    normalized = re.sub(r'_+', '_', normalized)
    # Eliminar underscores al inicio y final
    return normalized.strip('_')

def remove_accents(text: str) -> str:
    """
    Elimina tildes y acentos de un texto.
    """
    if not text:
        return ''
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

def normalize_country_std(country: str) -> str:
    """
    Normaliza país a lowercase canonical.
    Ej: "Peru" → "peru", "Perú" → "peru"
    """
    if not country:
        return ''
    # Eliminar tildes, convertir a lowercase, trim
    normalized = remove_accents(country.strip().lower())
    return normalized

def normalize_city_std(city: str) -> str:
    """
    Normaliza ciudad a lowercase + sin tildes + trim.
    Ej: "Lima" → "lima", "Lima " → "lima", "Líma" → "lima"
    """
    if not city:
        return ''
    # Eliminar tildes, convertir a lowercase, trim
    normalized = remove_accents(city.strip().lower())
    return normalized

def normalize_line_of_business_std(line: str) -> str:
    """
    Normaliza línea de negocio a snake_case.
    Ej: "Auto Taxi" → "auto_taxi", "Delivery" → "delivery"
    """
    if not line:
        return ''
    return normalize_to_snake_case(line)

def normalize_tipo_servicio_to_line_of_business(tipo_servicio: str) -> Optional[str]:
    """
    Mapea tipo_servicio (de trips_all) a línea de negocio requerida.
    Retorna la línea de negocio normalizada o None si no hay mapeo.
    """
    if not tipo_servicio:
        return None
    
    tipo_servicio_lower = tipo_servicio.strip().lower()
    
    if tipo_servicio_lower in TIPO_SERVICIO_MAPPING:
        return TIPO_SERVICIO_MAPPING[tipo_servicio_lower]
    
    tipo_servicio_sin_acentos = remove_accents(tipo_servicio_lower)
    if tipo_servicio_sin_acentos in TIPO_SERVICIO_MAPPING:
        return TIPO_SERVICIO_MAPPING[tipo_servicio_sin_acentos]
    
    return None

@dataclass
class LineOfBusinessResolution:
    line_of_business_base: Optional[str]
    resolution_source: Literal['tipo_servicio', 'default_lob', 'unknown']
    tipo_servicio_raw: Optional[str]
    default_lob_raw: Optional[str]
    is_unmapped_tipo_servicio: bool
    is_conflict: bool
    pago_corporativo_raw: Any
    is_b2b: bool
    segment: Literal['b2b', 'b2c']
    lob_bucket: Optional[str]

def resolve_lob_with_meta(
    tipo_servicio: Optional[str] = None,
    default_lob: Optional[str] = None,
    pago_corporativo: Any = None
) -> LineOfBusinessResolution:
    """
    Resuelve la línea de negocio para un viaje con metadata completa.
    
    Reglas:
    - Prioridad: tipo_servicio (si mapea) → default_lob → unknown
    - is_conflict=True si tipo_servicio_mapped != None AND default_lob != None AND difieren normalizados
    - is_b2b: True si pago_corporativo tiene valor (no null, no '', no '0', no 'false')
    - segment: 'b2b' si is_b2b else 'b2c'
    - lob_bucket: "{lob_base} - {segment}" si lob_base existe, sino None
    """
    tipo_servicio_raw = tipo_servicio
    default_lob_raw = default_lob
    pago_corporativo_raw = pago_corporativo
    
    tipo_servicio_normalized = None
    if tipo_servicio:
        tipo_servicio_normalized = remove_accents(tipo_servicio.strip().lower())
    
    default_lob_normalized = None
    if default_lob:
        default_lob_normalized = remove_accents(default_lob.strip().lower())
    
    lob_from_tipo = normalize_tipo_servicio_to_line_of_business(tipo_servicio) if tipo_servicio else None
    is_unmapped_tipo_servicio = False
    
    if tipo_servicio and not lob_from_tipo:
        is_unmapped_tipo_servicio = True
    
    line_of_business_base = None
    resolution_source: Literal['tipo_servicio', 'default_lob', 'unknown'] = 'unknown'
    
    if lob_from_tipo:
        line_of_business_base = lob_from_tipo
        resolution_source = 'tipo_servicio'
    elif default_lob:
        line_of_business_base = default_lob.strip()
        resolution_source = 'default_lob'
    
    is_conflict = False
    if lob_from_tipo and default_lob:
        lob_from_tipo_norm = remove_accents(lob_from_tipo.strip().lower())
        default_lob_norm = remove_accents(default_lob.strip().lower())
        if lob_from_tipo_norm != default_lob_norm:
            is_conflict = True
    
    if isinstance(pago_corporativo, bool):
        is_b2b = pago_corporativo
    elif pago_corporativo is None:
        is_b2b = False
    else:
        pago_str = str(pago_corporativo).strip()
        is_b2b = pago_str not in ('', '0', 'false', 'False')
    
    segment: Literal['b2b', 'b2c'] = 'b2b' if is_b2b else 'b2c'
    
    lob_bucket = None
    if line_of_business_base:
        lob_bucket = f"{line_of_business_base} - {segment}"
    
    return LineOfBusinessResolution(
        line_of_business_base=line_of_business_base,
        resolution_source=resolution_source,
        tipo_servicio_raw=tipo_servicio_raw,
        default_lob_raw=default_lob_raw,
        is_unmapped_tipo_servicio=is_unmapped_tipo_servicio,
        is_conflict=is_conflict,
        pago_corporativo_raw=pago_corporativo_raw,
        is_b2b=is_b2b,
        segment=segment,
        lob_bucket=lob_bucket
    )

def resolve_line_of_business_from_trip(
    tipo_servicio: Optional[str] = None,
    default_line_of_business: Optional[str] = None
) -> Optional[str]:
    """
    Resuelve la línea de negocio para un viaje usando prioridad:
    1. tipo_servicio (si existe) → mapear usando TIPO_SERVICIO_MAPPING
    2. default_line_of_business (del park)
    
    Retorna la línea de negocio normalizada o None si no se puede determinar.
    
    NOTA: Esta función es wrapper de compatibilidad.
    Usar resolve_lob_with_meta() para obtener metadata completa.
    """
    resolution = resolve_lob_with_meta(
        tipo_servicio=tipo_servicio,
        default_lob=default_line_of_business,
        pago_corporativo=None
    )
    return resolution.line_of_business_base

