"""
Constantes y reglas de severidad para huecos de margen en fuente (REAL).
Ver docs/REAL_MARGIN_SOURCE_GAP_CANONICAL_DEFINITION.md.
"""
# Anomalía principal: completados sin margen
MARGIN_GAP_PCT_WARNING = 0.5   # completed_without_margin_pct > 0.5% -> WARNING
MARGIN_GAP_PCT_CRITICAL = 2.0  # completed_without_margin_pct > 2% -> CRITICAL
# CRITICAL inmediato: días recientes con completed_trips > 0 y completed_trips_with_margin = 0

# Anomalía secundaria: cancelados con margen
CANCELLED_WITH_MARGIN_PCT_WARNING = 5.0   # cancelled_with_margin_pct > 5% -> WARNING
CANCELLED_WITH_MARGIN_PCT_CRITICAL = 10.0  # cancelled_with_margin_pct > 10% -> CRITICAL

ALERT_CODE_PRIMARY = "REAL_MARGIN_SOURCE_GAP_COMPLETED"
ALERT_CODE_SECONDARY = "REAL_CANCELLED_WITH_MARGIN"


def severity_completed_without_margin(
    completed_trips: int,
    completed_trips_without_margin: int,
    completed_trips_with_margin: int,
) -> str:
    """
    INFO / WARNING / CRITICAL para anomalía principal.
    CRITICAL si hay días con completed_trips > 0 y completed_trips_with_margin = 0 (cobertura 0%).
    """
    if completed_trips == 0:
        return "OK"
    pct = 100.0 * completed_trips_without_margin / completed_trips
    if completed_trips_with_margin == 0 and completed_trips > 0:
        return "CRITICAL"
    if pct >= MARGIN_GAP_PCT_CRITICAL:
        return "CRITICAL"
    if pct >= MARGIN_GAP_PCT_WARNING:
        return "WARNING"
    if pct > 0:
        return "INFO"
    return "OK"


def severity_cancelled_with_margin(
    cancelled_trips: int,
    cancelled_trips_with_margin: int,
) -> str:
    """WARNING / CRITICAL para anomalía secundaria (cancelados con margen)."""
    if cancelled_trips == 0:
        return "OK"
    pct = 100.0 * cancelled_trips_with_margin / cancelled_trips
    if pct >= CANCELLED_WITH_MARGIN_PCT_CRITICAL:
        return "CRITICAL"
    if pct >= CANCELLED_WITH_MARGIN_PCT_WARNING:
        return "WARNING"
    return "OK"
