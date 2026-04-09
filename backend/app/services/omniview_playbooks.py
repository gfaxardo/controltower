"""
Playbooks operativos Omniview — mapper explícito issue_code → acción (sin IA).

Se integra en el banner ejecutivo y puede consumirse el Inspector (frontend).
"""
from __future__ import annotations

from typing import Any, Optional

OMNIVIEW_OPERATIONAL_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "DAY_FACT_DATE_GAPS": {
        "issue_code": "DAY_FACT_DATE_GAPS",
        "operational_meaning": "Hay días sin fila en day_fact respecto al calendario esperado; los períodos pueden aparecer STALE o incompletos.",
        "recommended_action": "Ejecutar backfill incremental del loader diario para el rango afectado y validar jobs ETL.",
        "suggested_process": "1) validate_omniview_matrix_integrity 2) re-run carga day/week 3) verificar que MAX(trip_date) por período cubre el cierre calendario.",
        "priority": "P2",
        "owner_hint": "data_platform",
        "query_template": (
            "SELECT trip_date, COUNT(*) FROM ops.real_business_slice_day_fact "
            "WHERE trip_date >= CURRENT_DATE - 120 GROUP BY 1 ORDER BY 1 DESC LIMIT 200;"
        ),
    },
    "ROLLUP_MISMATCH": {
        "issue_code": "ROLLUP_MISMATCH",
        "operational_meaning": "La suma agregada en facts no reconcilia con el universo resolved (rollups / duplicados / filtros).",
        "recommended_action": "Reconciliar month_fact vs agregado sobre resolved para el mes indicado.",
        "suggested_process": "Auditar duplicados por dimensión; refrescar MV mensual; re-ejecutar load incremental del mes.",
        "priority": "P1",
        "owner_hint": "analytics_engineering",
        "query_template": (
            "SELECT month, SUM(trips_completed), SUM(revenue_yego_net) FROM ops.real_business_slice_month_fact "
            "WHERE month >= date_trunc('month', CURRENT_DATE)::date - interval '24 months' GROUP BY 1 ORDER BY 1;"
        ),
    },
    "MONTH_TRIPS_MISMATCH": {
        "issue_code": "MONTH_TRIPS_MISMATCH",
        "operational_meaning": "Conteo de viajes completados en month_fact no coincide con resolved para el mismo mes.",
        "recommended_action": "Reconciliar trips_completed: month_fact vs v_real_trips_business_slice_resolved.",
        "suggested_process": "Revalidar reglas de completado; re-cargar mes en month_fact.",
        "priority": "P1",
        "owner_hint": "data_platform",
        "query_template": (
            "SELECT trip_month, COUNT(*) FILTER (WHERE completed_flag) "
            "FROM ops.v_real_trips_business_slice_resolved WHERE resolution_status='resolved' "
            "GROUP BY 1 ORDER BY 1 DESC LIMIT 24;"
        ),
    },
    "MONTH_REVENUE_MISMATCH": {
        "issue_code": "MONTH_REVENUE_MISMATCH",
        "operational_meaning": "Revenue neto agregado no coincide con la suma desde viajes resueltos.",
        "recommended_action": "Reconciliar SUM(revenue_yego_net) en facts vs resolved por mes.",
        "suggested_process": "Revisar comisiones y filtros de revenue; re-ejecutar load del mes.",
        "priority": "P1",
        "owner_hint": "finance_ops",
        "query_template": (
            "SELECT trip_month, SUM(revenue_yego_net) FILTER (WHERE completed_flag) "
            "FROM ops.v_real_trips_business_slice_resolved WHERE resolution_status='resolved' "
            "GROUP BY 1 ORDER BY 1 DESC LIMIT 24;"
        ),
    },
    "REVENUE_WITHOUT_COMPLETED": {
        "issue_code": "REVENUE_WITHOUT_COMPLETED",
        "operational_meaning": "Hay revenue agregado sin viajes completados en la definición operativa.",
        "recommended_action": "Corregir agregación day_fact o definición de completed_flag en fuente.",
        "suggested_process": "Inspeccionar filas con revenue_yego_net <> 0 y trips_completed = 0; alinear con contrato.",
        "priority": "P2",
        "owner_hint": "analytics_engineering",
        "query_template": (
            "SELECT trip_date, city, business_slice_name, trips_completed, revenue_yego_net "
            "FROM ops.real_business_slice_day_fact WHERE trip_date >= CURRENT_DATE - 400 "
            "AND COALESCE(trips_completed,0)=0 AND revenue_yego_net IS NOT NULL AND revenue_yego_net <> 0 LIMIT 50;"
        ),
    },
    "DERIVED_BEHIND_SOURCE": {
        "issue_code": "DERIVED_BEHIND_SOURCE",
        "operational_meaning": "Los facts derivados van detrás del universo enriched (RAW); riesgo de frescura y períodos STALE aparentes.",
        "recommended_action": "Ejecutar loaders incrementales day/week y reducir lag fuente→fact.",
        "suggested_process": "Comparar MAX(trip_date) day_fact vs enriched_base; acelerar pipeline o ventana de carga.",
        "priority": "P2",
        "owner_hint": "data_platform",
        "query_template": (
            "SELECT MAX(trip_date) AS max_day_fact FROM ops.real_business_slice_day_fact; "
            "SELECT MAX(trip_date) AS max_enriched FROM ops.v_real_trips_enriched_base WHERE trip_date >= CURRENT_DATE - 400;"
        ),
    },
    "FACTS_UNREADABLE": {
        "issue_code": "FACTS_UNREADABLE",
        "operational_meaning": "No se puede leer de forma fiable la capa fact; la Matrix no es confiable para decisiones.",
        "recommended_action": "Restaurar acceso a ops.real_business_slice_*_fact y validar migraciones.",
        "suggested_process": "Verificar permisos de rol app; despliegue de migraciones 116/119; smoke test de lectura.",
        "priority": "P1",
        "owner_hint": "platform",
        "query_template": (
            "SELECT to_regclass('ops.real_business_slice_day_fact'), to_regclass('ops.real_business_slice_month_fact');"
        ),
    },
    "SOURCE_MAX_UNAVAILABLE": {
        "issue_code": "SOURCE_MAX_UNAVAILABLE",
        "operational_meaning": "No hay referencia de máximo en fuente acotada; freshness y comparativos pierden ancla.",
        "recommended_action": "Restaurar lectura de fuente canónica (trips / enriched) para bounded MAX.",
        "suggested_process": "Revisar vistas trips_unified / enriched_base y permisos.",
        "priority": "P3",
        "owner_hint": "data_platform",
        "query_template": "SELECT MAX(fecha_inicio_viaje::date) FROM public.trips_unified WHERE fecha_inicio_viaje IS NOT NULL;",
    },
    "COVERAGE_LOW": {
        "issue_code": "COVERAGE_LOW",
        "operational_meaning": "Bajo ratio mapped/total en el universo RAW real; parte del volumen no tiene slice asignado.",
        "recommended_action": "Priorizar reglas de mapping (park / tipo_servicio / works_terms) y cerrar huecos.",
        "suggested_process": "Revisar ops.business_slice_mapping_rules y cola de unmatched/conflict.",
        "priority": "P2",
        "owner_hint": "business_ops",
        "query_template": (
            "SELECT resolution_status, COUNT(*) FROM ops.v_real_trips_business_slice_resolved "
            "WHERE trip_date >= CURRENT_DATE - 90 GROUP BY 1;"
        ),
    },
    "UNMAPPED_HIGH": {
        "issue_code": "UNMAPPED_HIGH",
        "operational_meaning": "Muchos viajes en unmatched/conflict; el bucket UNMAPPED concentra volumen operativo.",
        "recommended_action": "Tratar cola de homologación: parks, tipo_servicio, works_terms.",
        "suggested_process": "Exportar unmatched recientes; iterar reglas; validar dim_park.",
        "priority": "P2",
        "owner_hint": "business_ops",
        "query_template": "SELECT * FROM ops.v_business_slice_unmatched_trips ORDER BY trip_date DESC LIMIT 50;",
    },
    "PERIOD_NOT_COMPARABLE": {
        "issue_code": "PERIOD_NOT_COMPARABLE",
        "operational_meaning": "El período no es comparable (abierto, parcial o calidad insuficiente); evitar decisiones sobre deltas definitivos.",
        "recommended_action": "Usar comparativos equivalentes o esperar cierre; no forzar ranking ejecutivo.",
        "suggested_process": "Revisar State Engine (OPEN/PARTIAL/STALE) y comparison_context en celda.",
        "priority": "P3",
        "owner_hint": "operator",
        "query_template": None,
    },
    "STALE_PERIOD": {
        "issue_code": "STALE_PERIOD",
        "operational_meaning": "Período histórico con carga incompleta vs calendario (max en período < fin esperado).",
        "recommended_action": "Backfill de datos en el rango del período o corregir pipeline para ese intervalo.",
        "suggested_process": "Verificar per_period_max_trip_date en meta Matrix vs expected_through_date.",
        "priority": "P2",
        "owner_hint": "data_platform",
        "query_template": (
            "SELECT date_trunc('month', trip_date)::date, MAX(trip_date) FROM ops.real_business_slice_day_fact "
            "GROUP BY 1 ORDER BY 1 DESC LIMIT 24;"
        ),
    },
}


def playbook_for_issue_code(issue_code: Optional[str]) -> Optional[dict[str, Any]]:
    if not issue_code:
        return None
    c = str(issue_code).strip()
    pb = OMNIVIEW_OPERATIONAL_PLAYBOOKS.get(c)
    if pb:
        return dict(pb)
    return {
        "issue_code": c,
        "operational_meaning": "Hallazgo de integridad; revisar mensaje del motor y evidencia adjunta.",
        "recommended_action": "Seguir el flujo sugerido en action_engine del hallazgo o validar con validate_omniview_matrix_integrity.",
        "suggested_process": "Documentar y escalar con trazabilidad (issue code + periodo).",
        "priority": "P3",
        "owner_hint": "operator",
        "query_template": None,
    }


def contextualize_playbook(
    pb: Optional[dict[str, Any]],
    ctx: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Añade período / ciudad / LOB / métrica a textos cuando el API ya las conoce."""
    if not pb:
        return None
    out = dict(pb)
    period = (ctx.get("period") or "").strip() or None
    city = (ctx.get("city") or "").strip() or None
    lob = (ctx.get("lob") or "").strip() or None
    metric = (ctx.get("metric") or "").strip() or None
    bits = [x for x in (period, city, lob) if x]
    if not bits and not metric:
        return out
    headline = " · ".join(bits)
    if metric:
        headline = f"{headline} · {metric}" if headline else metric
    ra = str(out.get("recommended_action") or "").strip()
    if ra and headline and headline not in ra:
        out["recommended_action"] = f"{ra} — {headline}"
    sp = str(out.get("suggested_process") or "").strip()
    if sp and headline and headline not in sp:
        out["suggested_process"] = f"{sp} Contexto operativo: {headline}."
    qt = out.get("query_template")
    if isinstance(qt, str) and headline:
        out["query_template"] = f"-- {headline}\n{qt}"
    out["playbook_context"] = {
        "period": period,
        "city": city,
        "lob": lob,
        "metric": metric or None,
    }
    return out
