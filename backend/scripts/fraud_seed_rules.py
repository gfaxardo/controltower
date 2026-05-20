"""Fase 1F — Seed idempotente de reglas antifraude en fraud.rule_catalog."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

from app.db.connection import get_db

RULES = [
    {
        "rule_code": "NEW_DRIVER_UNDER_50_TRIPS",
        "rule_name": "Driver nuevo con menos de 50 viajes",
        "description": "Driver con menos de 50 viajes completados historicos.",
        "severity_default": "medium",
        "weight": 20,
        "enabled": True,
    },
    {
        "rule_code": "HIGH_CARD_AMOUNT_NEW_DRIVER",
        "rule_name": "Monto alto con tarjeta en driver nuevo",
        "description": "Driver nuevo/no confiable con pago tarjeta y monto alto.",
        "severity_default": "high",
        "weight": 30,
        "enabled": True,
    },
    {
        "rule_code": "REPEATED_PICKUP_CLUSTER",
        "rule_name": "Cluster de origen repetido",
        "description": "Multiples viajes desde el mismo origen, geohash, cluster o direccion normalizada.",
        "severity_default": "high",
        "weight": 25,
        "enabled": True,
    },
    {
        "rule_code": "LONG_TRIP_OUTLIER",
        "rule_name": "Viaje atipico largo",
        "description": "Viaje con monto/distancia fuera del patron de ciudad/park.",
        "severity_default": "high",
        "weight": 25,
        "enabled": True,
    },
    {
        "rule_code": "SHORT_TRIP_BONUS_PATTERN",
        "rule_name": "Patron de viajes cortos para bono",
        "description": "Multiples viajes cortos/repetidos en ventana corta, posible abuso de bono referido.",
        "severity_default": "high",
        "weight": 30,
        "enabled": True,
    },
    {
        "rule_code": "BURST_ACTIVITY_NEW_DRIVER",
        "rule_name": "Actividad explosiva driver nuevo",
        "description": "Driver nuevo con cantidad anomala de viajes en pocas horas o dias.",
        "severity_default": "high",
        "weight": 25,
        "enabled": True,
    },
    {
        "rule_code": "PARK_CONCENTRATION_RISK",
        "rule_name": "Concentracion de riesgo por park",
        "description": "Concentracion de drivers sospechosos en un mismo park_id.",
        "severity_default": "medium",
        "weight": 20,
        "enabled": True,
    },
    {
        "rule_code": "POST_NEGATIVE_BALANCE_SIGNAL",
        "rule_name": "Senal de saldo negativo",
        "description": "Senal futura de saldo negativo posterior al viaje. DISABLED: sin fuente de saldo/PLAC.",
        "severity_default": "critical",
        "weight": 50,
        "enabled": False,
        "requires_source": '{"balance_source": true}',
    },
    {
        "rule_code": "BANK_ACCOUNT_CLUSTER",
        "rule_name": "Cluster de cuenta bancaria",
        "description": "Varios drivers asociados a misma cuenta bancaria, payout o identificador de pago.",
        "severity_default": "critical",
        "weight": 40,
        "enabled": True,
        "requires_source": '{"table": "public.payment_details", "required_columns": ["driver_id", "bank_name", "account_number"]}',
    },
    {
        "rule_code": "REFERRAL_BONUS_ABUSE_SIGNAL",
        "rule_name": "Abuso de bono por referido",
        "description": "Patron asociado a cumplimiento artificial de bono referido.",
        "severity_default": "high",
        "weight": 35,
        "enabled": False,
        "requires_source": '{"bonus_source": true}',
    },
    # ── Fase 1F-5: Statistical & Behavioral Trip Fraud Rules ──
    {
        "rule_code": "REPEATED_ORIGIN_PATTERN",
        "rule_name": "Patron de origen repetido",
        "description": "Multiples viajes desde el mismo origin_cluster_key en ventana corta. Indicativo de farming estacionario.",
        "severity_default": "high",
        "weight": 30,
        "enabled": True,
    },
    {
        "rule_code": "REPEATED_ROUTE_SIGNATURE",
        "rule_name": "Firma de ruta repetida",
        "description": "Misma ruta origen->destino repetida multiples veces. Compatible con farming de ruta fija.",
        "severity_default": "high",
        "weight": 35,
        "enabled": True,
    },
    {
        "rule_code": "SHORT_TRIP_FARMING_PATTERN",
        "rule_name": "Patron de farming con viajes cortos",
        "description": "Combinacion de viajes cortos, origen repetido, ruta repetida, densidad temporal y baja varianza. Senal fuerte de farming para bonos.",
        "severity_default": "critical",
        "weight": 40,
        "enabled": True,
    },
    {
        "rule_code": "ROUTE_LOOP_PATTERN",
        "rule_name": "Patron de bucle de ruta",
        "description": "Rutas tipo A->B, B->A repetidas. Indicativo de viajes sinteticos o simulados en pareja.",
        "severity_default": "high",
        "weight": 35,
        "enabled": True,
    },
    {
        "rule_code": "COORDINATED_ORIGIN_PATTERN",
        "rule_name": "Patron de origen coordinado",
        "description": "Multiples drivers distintos saliendo del mismo origen en ventana corta de tiempo.",
        "severity_default": "critical",
        "weight": 45,
        "enabled": True,
    },
    {
        "rule_code": "TIME_WINDOW_DENSITY",
        "rule_name": "Densidad en ventana temporal",
        "description": "Driver con densidad anomala de viajes en ventana D-1, D-7 o D-30 comparado contra baseline.",
        "severity_default": "high",
        "weight": 25,
        "enabled": True,
    },
    {
        "rule_code": "LOW_AVG_DISTANCE_PATTERN",
        "rule_name": "Distancia promedio baja",
        "description": "Distancia promedio por viaje significativamente por debajo del baseline del park/city/service_type.",
        "severity_default": "high",
        "weight": 35,
        "enabled": True,
    },
    {
        "rule_code": "LOW_AVG_DURATION_PATTERN",
        "rule_name": "Duracion promedio baja",
        "description": "Duracion promedio por viaje significativamente por debajo del baseline del park/city/service_type.",
        "severity_default": "high",
        "weight": 35,
        "enabled": True,
    },
    {
        "rule_code": "EXTREME_SHORT_TRIP_RATIO",
        "rule_name": "Ratio extremo de viajes cortos",
        "description": "Porcentaje de viajes cortos (< 2km o < 3 min) excesivamente alto respecto al total de viajes del driver.",
        "severity_default": "critical",
        "weight": 40,
        "enabled": True,
    },
    {
        "rule_code": "LOW_VARIANCE_PATTERN",
        "rule_name": "Patron de varianza baja",
        "description": "Varianza de distancia, duracion y/o monto extremadamente baja. Viajes demasiado uniformes para ser organicos.",
        "severity_default": "medium",
        "weight": 30,
        "enabled": True,
    },
    {
        "rule_code": "LONG_TRIP_OUTLIER_V2",
        "rule_name": "Viaje atipico largo (baseline)",
        "description": "Viaje con monto/distancia/duracion que excede significativamente el baseline estadistico del park/city.",
        "severity_default": "medium",
        "weight": 30,
        "enabled": True,
    },
    {
        "rule_code": "HIGH_CARD_AMOUNT_NEW_DRIVER_V2",
        "rule_name": "Monto alto tarjeta driver nuevo (baseline)",
        "description": "Driver nuevo con pago tarjeta y monto que excede el p90 del baseline. Version baseline-aware.",
        "severity_default": "critical",
        "weight": 35,
        "enabled": True,
    },
    {
        "rule_code": "BURST_ACTIVITY_NEW_DRIVER_V2",
        "rule_name": "Actividad explosiva driver nuevo (baseline)",
        "description": "Driver nuevo con volumen de viajes que excede significativamente el avg_trips_per_day del baseline.",
        "severity_default": "high",
        "weight": 30,
        "enabled": True,
    },
    {
        "rule_code": "PARK_CONCENTRATION_RISK_V2",
        "rule_name": "Concentracion de riesgo conductual por park",
        "description": "Concentracion de patrones sospechosos (behavioral) en un mismo park_id.",
        "severity_default": "high",
        "weight": 25,
        "enabled": True,
    },
]

def seed():
    with get_db() as conn:
        cur = conn.cursor()
        for rule in RULES:
            cur.execute("""
                INSERT INTO fraud.rule_catalog
                    (rule_code, rule_name, description, severity_default, weight, enabled, requires_source)
                VALUES (%(rc)s, %(rn)s, %(desc)s, %(sd)s, %(w)s, %(en)s, %(rs)s)
                ON CONFLICT (rule_code) DO UPDATE SET
                    rule_name = EXCLUDED.rule_name,
                    description = EXCLUDED.description,
                    severity_default = EXCLUDED.severity_default,
                    weight = EXCLUDED.weight,
                    enabled = EXCLUDED.enabled,
                    requires_source = COALESCE(EXCLUDED.requires_source, fraud.rule_catalog.requires_source),
                    updated_at = now()
            """, {
                "rc": rule["rule_code"],
                "rn": rule["rule_name"],
                "desc": rule.get("description", ""),
                "sd": rule["severity_default"],
                "w": rule["weight"],
                "en": rule["enabled"],
                "rs": rule.get("requires_source"),
            })
        conn.commit()
        cur.close()

    print(f"{len(RULES)} reglas seeded/actualizadas en fraud.rule_catalog")
    for r in RULES:
        status = "ENABLED" if r["enabled"] else "DISABLED"
        print(f"  {r['rule_code']} ({r['severity_default']}, w={r['weight']}) [{status}]")

if __name__ == "__main__":
    seed()
