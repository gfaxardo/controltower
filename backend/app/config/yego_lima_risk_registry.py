"""
YEGO Lima Growth — Risk Registry (LG-2.6 V1).

Deterministic risk definitions for executive panel.
NO predicciones. NO impacto. NO revenue.
"""

CAPACITY_RISK = "CAPACITY_RISK"
QUEUE_RISK = "QUEUE_RISK"
EXPORT_RISK = "EXPORT_RISK"
SYNC_RISK = "SYNC_RISK"
DATA_QUALITY_RISK = "DATA_QUALITY_RISK"

RISK_CODES = [
    CAPACITY_RISK,
    QUEUE_RISK,
    EXPORT_RISK,
    SYNC_RISK,
    DATA_QUALITY_RISK,
]

RISK_THRESHOLDS = {
    CAPACITY_RISK: {
        "description": "Capacidad operativa insuficiente vs oportunidades",
        "green_max": 1.0,
        "yellow_min": 0.80,
        "red_below": 0.80,
    },
    QUEUE_RISK: {
        "description": "Tasa de HELD elevada en assignment queue",
        "green_max": 0.05,
        "yellow_min": 0.05,
        "yellow_max": 0.15,
        "red_above": 0.15,
    },
    EXPORT_RISK: {
        "description": "Tasa de exportacion baja desde READY a LoopControl",
        "green_min": 0.90,
        "yellow_min": 0.70,
        "red_below": 0.70,
    },
    SYNC_RISK: {
        "description": "Alta tasa de resultados no emparejados con queue",
        "green_max": 0.05,
        "yellow_min": 0.05,
        "yellow_max": 0.15,
        "red_above": 0.15,
    },
    DATA_QUALITY_RISK: {
        "description": "Datos faltantes en assignment queue",
        "green_max": 0.02,
        "yellow_min": 0.02,
        "yellow_max": 0.10,
        "red_above": 0.10,
    },
}


def evaluate_level(risk_code: str, value: float) -> str:
    thresholds = RISK_THRESHOLDS[risk_code]

    if risk_code == CAPACITY_RISK:
        if value >= thresholds["green_max"]:
            return "GREEN"
        elif value >= thresholds["red_below"]:
            return "YELLOW"
        else:
            return "RED"

    if risk_code in (QUEUE_RISK, SYNC_RISK, DATA_QUALITY_RISK):
        if value <= thresholds["green_max"]:
            return "GREEN"
        elif value <= thresholds["yellow_max"]:
            return "YELLOW"
        else:
            return "RED"

    if risk_code == EXPORT_RISK:
        if value >= thresholds["green_min"]:
            return "GREEN"
        elif value >= thresholds["red_below"]:
            return "YELLOW"
        else:
            return "RED"

    return "GREEN"


def evaluate_score(risk_code: str, value: float) -> float:
    level = evaluate_level(risk_code, value)

    if risk_code == CAPACITY_RISK:
        if level == "GREEN":
            return round(min(1.0, value), 2)
        elif level == "YELLOW":
            return round(0.5 + (value - 0.8) * 2.5, 2)
        else:
            return round(max(0.0, value), 2)

    if risk_code in (QUEUE_RISK, SYNC_RISK, DATA_QUALITY_RISK):
        if level == "GREEN":
            return round(max(0.0, 1.0 - value * 10), 2)
        elif level == "YELLOW":
            return round(max(0.2, 1.0 - value * 5), 2)
        else:
            return round(1.0 - value, 2)

    if risk_code == EXPORT_RISK:
        if level == "GREEN":
            return round(min(1.0, value), 2)
        elif level == "YELLOW":
            return round(value * 0.8, 2)
        else:
            return round(value * 0.5, 2)

    return 1.0
