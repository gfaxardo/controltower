"""
YEGO Lima Growth — Operational Truth Service (LG-UX-R2.1)

Adds metadata to every KPI: source, freshness, layer_date, effective_source_date,
explanation, remediation, confidence. No new calculations. Only metadata aggregation.
"""
from __future__ import annotations
import logging
from datetime import date as DateType, datetime, timezone
from typing import Any, Dict, List, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)

KPI_DEFINITIONS = {
    "universe_total": {
        "label": "Total Universe",
        "source_table": "growth.yango_lima_driver_state_snapshot",
        "source_date_col": "snapshot_date",
        "layer": "snapshot",
        "explanation_template": "Total de conductores en el snapshot del dia {date}.",
    },
    "eligible_total": {
        "label": "Elegibles",
        "source_table": "growth.yango_lima_program_eligibility_daily",
        "source_date_col": "eligibility_date",
        "layer": "eligibility",
        "explanation_template": "Conductores elegibles para al menos un programa en {date}.",
    },
    "prioritized_total": {
        "label": "Priorizados",
        "source_table": "growth.yango_lima_prioritized_opportunity_daily",
        "source_date_col": "opportunity_date",
        "layer": "prioritized",
        "explanation_template": "Conductores priorizados (scored + ranked) para {date}.",
    },
    "actionable_today": {
        "label": "Accionables Hoy",
        "source_table": "growth.yango_lima_prioritized_opportunity_daily",
        "source_date_col": "opportunity_date",
        "filter": "is_actionable_today = true",
        "layer": "prioritized",
        "explanation_template": "Priorizados dentro del capacity cap ({capacity}) para {date}.",
    },
    "queue_total": {
        "label": "Queue Total",
        "source_table": "growth.yego_lima_assignment_queue",
        "source_date_col": "assignment_date",
        "layer": "queue",
        "explanation_template": "Total de conductores en la cola operativa para {date}.",
    },
    "queue_ready": {
        "label": "Queue READY",
        "source_table": "growth.yego_lima_assignment_queue",
        "source_date_col": "assignment_date",
        "filter": "queue_status = 'READY'",
        "layer": "queue",
        "explanation_template": "Conductores listos para exportar a campana en {date}.",
    },
    "queue_held": {
        "label": "Queue HELD",
        "source_table": "growth.yego_lima_assignment_queue",
        "source_date_col": "assignment_date",
        "filter": "queue_status = 'HELD'",
        "layer": "queue",
        "explanation_template": "Conductores retenidos (sin telefono o canal) en {date}.",
    },
    "queue_exported": {
        "label": "Queue EXPORTED",
        "source_table": "growth.yego_lima_assignment_queue",
        "source_date_col": "assignment_date",
        "filter": "queue_status = 'EXPORTED'",
        "layer": "queue",
        "explanation_template": "Conductores ya exportados a LoopControl para {date}.",
    },
    "lc_campaigns": {
        "label": "LoopControl Campaigns",
        "source_table": "growth.yango_lima_loopcontrol_campaign_export",
        "layer": "export",
        "explanation_template": "Campanas exportadas a LoopControl.",
    },
    "lc_contacts": {
        "label": "LoopControl Contacts",
        "source_table": "growth.yango_lima_loopcontrol_campaign_export",
        "layer": "export",
        "explanation_template": "Contactos enviados a LoopControl.",
    },
    "capacity_total": {
        "label": "Capacidad Total",
        "source_table": "growth.yango_lima_opportunity_policy_config",
        "layer": "config",
        "explanation_template": "Capacidad diaria configurada para accion.",
    },
    "intraday_signals": {
        "label": "Senales Intradia",
        "source_table": "growth.yego_lima_intraday_driver_signal",
        "source_date_col": "signal_date",
        "layer": "intraday",
        "explanation_template": "Senales de actividad post-accion observadas para {date}.",
    },
}


def get_operational_truth(date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        kpis = []
        warnings = []

        # Get freshness chain for layer metadata
        try:
            from app.services.yego_lima_freshness_chain_service import get_freshness_chain_status
            freshness = get_freshness_chain_status()
            layer_map = {l["layer"]: l for l in freshness.get("layers", [])}
        except Exception:
            freshness = {"layers": []}
            layer_map = {}

        # Get latest operational dates
        try:
            from app.services.yego_lima_daily_refresh_service import detect_latest_closed_data_date
            date_info = detect_latest_closed_data_date()
            latest_op_date = date_info.get("operational_data_date")
        except Exception:
            latest_op_date = None

        for key, defn in KPI_DEFINITIONS.items():
            table = defn["source_table"]
            col = defn.get("source_date_col")
            filt = defn.get("filter", "")
            layer_name = defn["layer"]

            kpi = {
                "key": key,
                "label": defn["label"],
                "value": 0,
                "source_table": table,
                "layer": layer_name,
                "confidence": "HIGH",
            }

            # Get value
            try:
                where = f"WHERE {col} = %(d)s" if col else ""
                if filt:
                    where += f" AND {filt}" if where else f"WHERE {filt}"
                sql = f"SELECT COUNT(*) FROM {table} {where}"
                cur.execute(sql, {"d": date})
                kpi["value"] = cur.fetchone()[0] or 0
            except Exception as e:
                kpi["value"] = -1
                kpi["error"] = str(e)[:80]
                kpi["confidence"] = "UNKNOWN"

            # Get latest data date for this table
            if col:
                try:
                    cur.execute(f"SELECT MAX({col}), COUNT(*) FROM {table}")
                    r = cur.fetchone()
                    kpi["latest_data_date"] = str(r[0]) if r[0] else None
                    kpi["total_rows"] = r[1] or 0
                except Exception:
                    kpi["latest_data_date"] = None

            # Layer metadata from freshness chain
            layer_meta = layer_map.get(layer_name, {})
            if layer_meta:
                kpi["layer_date"] = layer_meta.get("layer_date")
                kpi["effective_source_date"] = layer_meta.get("effective_source_date")
                kpi["freshness_status"] = layer_meta.get("effective_freshness", "UNKNOWN")
            else:
                kpi["layer_date"] = None
                kpi["effective_source_date"] = None
                kpi["freshness_status"] = "UNKNOWN"

            # Determine explanation and status
            value = kpi["value"]
            latest = kpi.get("latest_data_date")
            freshness = kpi.get("freshness_status", "UNKNOWN")

            if value == -1:
                kpi["status"] = "ERROR"
                kpi["explanation"] = f"Error consultando {table}: {kpi.get('error', '')}"
                kpi["remediation"] = "Verificar tabla y conexion DB."
                kpi["confidence"] = "UNKNOWN"
            elif value == 0 and latest and latest < date:
                kpi["status"] = "NOT_GENERATED"
                kpi["explanation"] = f"{defn['label']} es 0 porque no hay datos para {date}. Ultima fecha con datos: {latest}."
                kpi["remediation"] = f"Ejecutar pipeline diario para {date}: POST /pipeline/run-daily"
                kpi["confidence"] = "HIGH"
                warnings.append({
                    "kpi": key,
                    "type": "NOT_GENERATED",
                    "message": kpi["explanation"],
                })
            elif value == 0 and (not latest or latest == date):
                kpi["status"] = "VALID_ZERO"
                kpi["explanation"] = f"{defn['label']} es 0 para {date}. Es un cero real (no hay datos para esta fecha)."
                kpi["remediation"] = None
                kpi["confidence"] = "HIGH"
            elif freshness == "STALE_PROPAGATED":
                kpi["status"] = "STALE_PROPAGATED"
                kpi["explanation"] = f"{defn['label']} muestra {value} pero los datos fuente son de {kpi.get('effective_source_date', '?')}, no de {date}."
                kpi["remediation"] = "Actualizar fuente de datos (Yango API / history bootstrap)."
                warnings.append({
                    "kpi": key,
                    "type": "STALE_PROPAGATED",
                    "message": kpi["explanation"],
                })
            else:
                kpi["status"] = freshness if freshness != "UNKNOWN" else "OK"
                kpi["explanation"] = defn["explanation_template"].format(date=date)
                kpi["remediation"] = None

            kpis.append(kpi)

        # Overall status
        statuses = [k["status"] for k in kpis]
        if "ERROR" in statuses:
            overall = "ERROR"
        elif "NOT_GENERATED" in statuses:
            overall = "WARNING"
        elif "STALE_PROPAGATED" in statuses:
            overall = "WARNING"
        elif all(s in ("FRESH", "OK", "VALID_ZERO", "RAW") for s in statuses):
            overall = "OK"
        else:
            overall = "WARNING"

    return {
        "date": date,
        "overall_status": overall,
        "latest_operational_date": latest_op_date,
        "kpis": kpis,
        "warnings": warnings,
        "total_kpis": len(kpis),
        "warnings_count": len(warnings),
    }
