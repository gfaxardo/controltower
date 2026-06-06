"""
Explainability Service — LG-UX-R2.3

Deterministic explainability for Lima Growth KPIs.
Takes KPI values + freshness + context → generates human-readable explanations.
No AI. No inference. Pure deterministic rules.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EXPLAINABILITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "universe_total": {
        "title": "Universo Total",
        "definition": "Total de conductores activos en el state snapshot mas reciente.",
        "calculation": "COUNT(DISTINCT driver_profile_id) FROM growth.yango_lima_driver_state_snapshot WHERE snapshot_date = MAX(snapshot_date)",
    },
    "eligible_total": {
        "title": "Elegibles",
        "definition": "Conductores que cumplen criterios para al menos un programa operativo.",
        "calculation": "COUNT(DISTINCT driver_profile_id) FROM growth.yango_lima_program_eligibility_daily WHERE eligibility_date = fecha",
    },
    "prioritized_total": {
        "title": "Priorizados",
        "definition": "Conductores con programa asignado y ranking de prioridad definido por el policy engine.",
        "calculation": "COUNT(*) FROM growth.yango_lima_prioritized_opportunity_daily WHERE opportunity_date = fecha",
    },
    "actionable_today": {
        "title": "Accionables Hoy",
        "definition": "Conductores priorizados que estan dentro del daily_action_capacity y son accionables hoy.",
        "calculation": "prioritized_total WHERE is_actionable_today = true. Limitado por daily_action_capacity.",
    },
    "daily_action_capacity": {
        "title": "Daily Action Capacity",
        "definition": "Limite maximo de conductores accionables por dia definido en la politica activa.",
        "calculation": "daily_action_capacity FROM growth.yango_lima_opportunity_policy_config WHERE is_active = true",
    },
    "capacity_total": {
        "title": "Capacidad Diaria",
        "definition": "Capacidad operativa total sumando agentes x capacidad por agente en todos los canales.",
        "calculation": "SUM(agents * capacity_per_agent) FROM growth.yango_lima_capacity_config WHERE is_active = true",
    },
    "queue_total": {
        "title": "En Cola",
        "definition": "Total de conductores en la cola de asignacion para la fecha actual.",
        "calculation": "COUNT(*) FROM growth.yango_lima_assignment_queue WHERE assignment_date = fecha",
    },
    "queue_ready": {
        "title": "READY",
        "definition": "Conductores en cola listos para ser exportados (tienen telefono y canal asignado).",
        "calculation": "COUNT(*) WHERE queue_status = 'READY'",
    },
    "queue_held": {
        "title": "HELD",
        "definition": "Conductores en cola retenidos (sin telefono o sin canal asignado).",
        "calculation": "COUNT(*) WHERE queue_status = 'HELD'",
    },
    "loopcontrol_contacts_inserted": {
        "title": "Contactos Exportados",
        "definition": "Total de contactos insertados exitosamente en LoopControl a traves de todas las campanas.",
        "calculation": "SUM(contacts_inserted) FROM growth.yango_lima_loopcontrol_campaign_export WHERE export_status = 'exported'",
    },
    "loopcontrol_campaigns_exported": {
        "title": "Campanas Exportadas",
        "definition": "Numero de campanas DRAFT exportadas exitosamente a LoopControl.",
        "calculation": "COUNT(*) FROM growth.yango_lima_loopcontrol_campaign_export WHERE export_status = 'exported'",
    },
    "driver_snapshot": {
        "title": "Driver State Snapshot",
        "definition": "Fotografia diaria del estado de cada conductor: lifecycle, performance, retention.",
        "calculation": "Generado desde driver_state_snapshot table. Agrupa por lifecycle_state, performance_state, retention_state.",
    },
    "total_drivers": {
        "title": "Total Drivers",
        "definition": "Numero total de conductores en el state snapshot mas reciente.",
        "calculation": "COUNT(*) FROM growth.yango_lima_driver_state_snapshot WHERE snapshot_date = MAX(snapshot_date)",
    },
}


def explain_kpi(
    kpi_key: str,
    current_value: Any = None,
    freshness: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    registry = EXPLAINABILITY_REGISTRY.get(kpi_key, {})
    context = context or {}

    definition = registry.get("definition", f"Metrica operacional: {kpi_key}")
    calculation = registry.get("calculation", "Calculo desde fuente de datos operacional")
    title = registry.get("title", kpi_key)

    val_num = None
    if current_value is not None:
        try:
            val_num = int(current_value) if current_value != "" else None
        except (ValueError, TypeError):
            val_num = current_value

    reason = _build_reason(kpi_key, val_num, freshness, context)
    op_meaning = _build_operational_meaning(kpi_key, val_num, freshness)
    remediation = _build_remediation(kpi_key, val_num, freshness, context)
    dependencies = _build_dependencies(kpi_key, context)

    return {
        "title": title,
        "definition": definition,
        "calculation": calculation,
        "current_value": current_value,
        "reason": reason,
        "operational_meaning": op_meaning,
        "dependencies": dependencies,
        "freshness_status": freshness.get("status") if freshness else None,
        "remediation": remediation,
    }


def _build_reason(kpi_key: str, val: Any, freshness: Optional[Dict], ctx: Dict) -> str:
    f_status = freshness.get("status") if freshness else None

    if f_status == "UNKNOWN":
        return f"El valor de {kpi_key} no puede certificarse completamente porque la fuente no tiene timestamp de actualizacion."
    if f_status == "STALE":
        age = freshness.get("age_minutes", "?")
        return f"El valor de {kpi_key} puede estar desactualizado. La fuente tiene {age}min de antiguedad (limite: {freshness.get('threshold_minutes', '?')}min)."

    if kpi_key == "eligible_total":
        if val == 0:
            universe = ctx.get("universe_total", 0)
            if universe == 0:
                return "Eligible es 0 porque no hay universo disponible (driver state snapshot vacio)."
            return "Hay universo disponible, pero ningun conductor cumple los criterios de elegibilidad actuales."
        return f"Hay {val} conductores que cumplen criterios de al menos un programa operativo."

    if kpi_key == "prioritized_total":
        if val == 0:
            eligible = ctx.get("eligible_total", 0)
            if eligible == 0:
                return "No hay priorizados porque no hay elegibles."
            return "Existen elegibles, pero ninguno cumple los criterios de priorizacion del policy engine."
        return f"{val} conductores tienen programa asignado y ranking de prioridad."

    if kpi_key == "actionable_today":
        cap = ctx.get("daily_action_capacity", 0)
        return f"{val} conductores son accionables hoy, limitado por daily_action_capacity = {cap}."

    if kpi_key == "queue_total":
        if val == 0:
            exported = ctx.get("loopcontrol_campaigns_exported", 0)
            actionable = ctx.get("actionable_today", 0)
            if exported > 0:
                return "La cola esta vacia porque los registros disponibles ya fueron exportados."
            if actionable == 0:
                return "La cola esta vacia porque no hay conductores accionables hoy."
            return "La cola esta vacia. Usa 'Construir Cola' para generarla."
        return f"Hay {val} conductores en la cola de asignacion."

    if kpi_key == "capacity_total":
        if val == 0 or val is None:
            return "No hay capacidad configurada. Configura agentes y capacidad por canal en la seccion Configuracion."
        return f"Capacidad operativa total de {val} gestiones diarias."

    if kpi_key in ("queue_ready",):
        if val == 0:
            return "No hay conductores READY en la cola. Revisa HELD para ver conductores sin telefono o canal."
        return f"{val} conductores listos para exportar."

    if kpi_key in ("queue_held",):
        if val == 0:
            return "No hay conductores HELD. Todos los registros tienen telefono y canal asignado."
        return f"{val} conductores retenidos (sin telefono o canal)."

    if kpi_key in ("loopcontrol_contacts_inserted", "loopcontrol_campaigns_exported"):
        if val == 0:
            return "No se han exportado contactos a LoopControl todavia."
        return f"Se han exportado {val} a LoopControl exitosamente."

    if kpi_key == "total_drivers":
        if val == 0:
            return "No hay conductores en el state snapshot. El pipeline de datos puede estar detenido."
        return f"State snapshot contiene {val} conductores."

    if f_status == "WARNING":
        return f"{val}. Nota: los datos tienen mas de {freshness.get('threshold_minutes', '?')}min de antiguedad."

    return f"Valor actual: {val}"


def _build_operational_meaning(kpi_key: str, val: Any, freshness: Optional[Dict]) -> str:
    if kpi_key == "actionable_today":
        return "Estos son los conductores que el equipo debe gestionar hoy. Si el numero es menor que la capacidad, hay margen para incorporar mas conductores."
    if kpi_key == "queue_total":
        return "La cola representa el trabajo pendiente de exportacion a LoopControl. READY = listo para exportar. HELD = necesita atencion."
    if kpi_key == "capacity_total":
        return "La capacidad limita cuantos conductores pueden gestionarse efectivamente. Si accionables > capacidad, hay un gap operativo."
    if kpi_key == "prioritized_total":
        return "Conductores que han pasado por el scoring y ranking del policy engine. Solo los top-N (daily_action_capacity) son accionables."
    if kpi_key in ("loopcontrol_contacts_inserted", "loopcontrol_campaigns_exported"):
        return "Contactos enviados al call center via LoopControl. Cada campana exportada genera un campaign_id_external."
    return "Metrifica operacional del pipeline Lima Growth."


def _build_remediation(kpi_key: str, val: Any, freshness: Optional[Dict], ctx: Dict) -> Optional[str]:
    f_status = freshness.get("status") if freshness else None

    if f_status == "STALE":
        return f"Refrescar la fuente de datos. Los datos tienen mas de {freshness.get('threshold_minutes', '?')}min."
    if f_status == "UNKNOWN":
        return "Configurar timestamp de actualizacion en la tabla fuente."

    if kpi_key == "queue_total" and (val == 0 or val is None):
        return "Ejecutar 'Construir Cola' desde la seccion Execution Queue."
    if kpi_key == "capacity_total" and (val == 0 or val is None):
        return "Configurar agentes y capacidad por canal en la pestana Configuracion."
    if kpi_key == "eligible_total" and val == 0:
        return "Verificar que el pipeline de program eligibility se haya ejecutado hoy (POST /programs/build-eligibility)."
    if kpi_key == "prioritized_total" and val == 0:
        return "Verificar que el policy engine haya generado priorizados hoy (POST /policy/build-prioritized-opportunities)."

    return None


def _build_dependencies(kpi_key: str, ctx: Dict) -> List[Dict[str, Any]]:
    deps = []
    if kpi_key == "actionable_today":
        deps.append({"name": "daily_action_capacity", "value": ctx.get("daily_action_capacity"), "status": "limit"})
        deps.append({"name": "prioritized_total", "value": ctx.get("prioritized_total"), "status": "source"})
    if kpi_key == "queue_total":
        deps.append({"name": "actionable_today", "value": ctx.get("actionable_today"), "status": "input"})
    if kpi_key == "prioritized_total":
        deps.append({"name": "eligible_total", "value": ctx.get("eligible_total"), "status": "input"})
    if kpi_key == "eligible_total":
        deps.append({"name": "universe_total", "value": ctx.get("universe_total"), "status": "input"})
    return deps
