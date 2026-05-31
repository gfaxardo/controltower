"""
Yego Pro Profitability — Fleet Project API
Prefix: /fleet-project/yego-pro/profitability

Phase 1 Foundation: read-only serving layer for historical profitability.
Control Foundation (serving layer). No forecast/suggestion/decision/action.

Park: 64085dd85e124e2c808806f70d527ea8 (Lima)
"""
from typing import Optional

from fastapi import APIRouter, Query, Body

from app.services.yego_pro_profitability_service import (
    get_overview,
    get_weekly,
    get_daily,
    get_drivers,
    get_vehicles,
    get_shifts,
    get_input_mapping,
    get_quality,
    get_root_cause_audit,
    get_diagnostics_drivers,
    get_diagnostics_vehicles,
    get_diagnostics_shifts,
    get_diagnostics_portfolio,
    run_simulator,
    get_simulator_defaults,
    get_bonus_config,
    save_bonus_config,
    reset_bonus_config_to_defaults,
    get_baseline_scenario,
    list_scenarios,
    save_scenario,
    update_scenario,
    duplicate_scenario,
    archive_scenario,
    get_operational_baseline,
    get_kpi_explainability,
    get_operational_references_real,
    get_driver_drill,
    get_vehicle_drill,
    PARK_ID,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fleet-project/yego-pro/profitability",
    tags=["yego-pro-profitability"],
)


@router.get("/overview")
def overview(
    park_id: str = Query(default=PARK_ID, description="Park ID (default: Yego Lima)"),
):
    """
    Overview KPIs: last 30 days trips + last closed billing week.
    Returns structured KPIs with source, metric_type, confidence metadata.
    """
    return get_overview(park_id=park_id)


@router.get("/weekly")
def weekly(
    park_id: str = Query(default=PARK_ID),
    weeks: int = Query(default=12, ge=1, le=52, description="Number of weeks to return"),
):
    """
    Weekly profitability from module_weekly_billing.
    Each row includes: revenue, costs, profit, productivity metrics.
    """
    return get_weekly(park_id=park_id, weeks=weeks)


@router.get("/daily")
def daily(
    park_id: str = Query(default=PARK_ID),
    days: int = Query(default=30, ge=1, le=90, description="Number of days to return"),
):
    """
    Daily profitability from trips_2026 (operational only, no financial).
    Includes day/night shift split per day.
    """
    return get_daily(park_id=park_id, days=days)


@router.get("/drivers")
def drivers(
    park_id: str = Query(default=PARK_ID),
    week_start: Optional[str] = Query(default=None, description="ISO date of week start (default: latest)"),
):
    """
    Driver-level profitability for a given week.
    Source: module_weekly_billing joined with drivers master.
    """
    return get_drivers(park_id=park_id, week_start=week_start)


@router.get("/vehicles")
def vehicles(
    park_id: str = Query(default=PARK_ID),
):
    """
    Vehicle fleet configuration and quota structure.
    LIMITED: no vehicle-to-driver assignment exists.
    """
    return get_vehicles(park_id=park_id)


@router.get("/shifts")
def shifts(
    park_id: str = Query(default=PARK_ID),
    weeks: int = Query(default=8, ge=1, le=26),
):
    """
    Day vs Night shift profitability (weekly aggregation).
    Source: trips_2026 with EXTRACT(HOUR) classification.
    """
    return get_shifts(park_id=park_id, days=weeks * 7)


@router.get("/input-mapping")
def input_mapping(
    park_id: str = Query(default=PARK_ID),
):
    """
    Input mapping: REAL / ASSUMPTION / NOT_AVAILABLE inputs.
    Includes payment tiers and configurable parameters.
    """
    return get_input_mapping(park_id=park_id)


@router.get("/quality")
def quality(
    park_id: str = Query(default=PARK_ID),
):
    """
    Data quality check: serving view existence, freshness, row counts.
    Returns overall health status for the profitability module.
    """
    return get_quality(park_id=park_id)


@router.get("/root-cause")
def root_cause(
    park_id: str = Query(default=PARK_ID),
):
    """
    Root cause audit: identifies missing records (production without close,
    close without production, missing plates, missing billing).
    Returns detailed driver-level and shift-level gap analysis.
    """
    return get_root_cause_audit(park_id=park_id)


@router.get("/diagnostics/drivers")
def diagnostics_drivers(
    park_id: str = Query(default=PARK_ID),
):
    """
    P1.5 Diagnostic Layer: driver-level deterministic diagnostics.
    Classifies each driver as PROFITABLE / RISKY / LOSS / UNKNOWN
    with causes, severity, confidence, and explanation.
    """
    return get_diagnostics_drivers(park_id=park_id)


@router.get("/diagnostics/vehicles")
def diagnostics_vehicles(
    park_id: str = Query(default=PARK_ID),
):
    """
    P1.5 Diagnostic Layer: vehicle-level deterministic diagnostics.
    Classifies each vehicle (by plate) as Rentable / Recuperable / Critico.
    Margin is estimated using park-level margin proxy.
    """
    return get_diagnostics_vehicles(park_id=park_id)


@router.get("/diagnostics/shifts")
def diagnostics_shifts(
    park_id: str = Query(default=PARK_ID),
):
    """
    P1.5 Diagnostic Layer: day vs night shift diagnostics.
    Compares revenue, trips, margin between shifts.
    Answers gap severity and hypothetical payout limits.
    """
    return get_diagnostics_shifts(park_id=park_id)


@router.get("/diagnostics/portfolio")
def diagnostics_portfolio(
    park_id: str = Query(default=PARK_ID),
):
    """
    P1.5 Diagnostic Layer: portfolio-level aggregation.
    Returns total margin, % in loss, top 5 losses/gains,
    concentration, and hypothetical impact of removing bottom entities.
    """
    return get_diagnostics_portfolio(park_id=park_id)


@router.post("/simulator/run")
def simulator_run(payload: dict = Body(...)):
    """
    P1.4.2 Simulator: ejecuta una simulacion completa de rentabilidad.
    Recibe todos los inputs editables y devuelve subtotales, calculation_trace,
    referencias operativas y escenarios de sensibilidad con bonos.
    """
    return run_simulator(payload)


@router.get("/simulator/defaults")
def simulator_defaults():
    """
    Devuelve las tablas de bonos hardcodeadas y los inputs por defecto
    para inicializar el Simulator UI.
    """
    return get_simulator_defaults()


@router.get("/simulator/bonus-config")
def bonus_config_get(
    park_id: str = Query(default=PARK_ID, description="Park ID"),
    config_name: str = Query(default="default", description="Config name"),
):
    """
    P1.4.4: Lee configuracion de bonos persistida.
    Si no existe en PostgreSQL devuelve defaults hardcodeados con status NOT_PERSISTED.
    """
    return get_bonus_config(park_id=park_id, config_name=config_name)


@router.post("/simulator/bonus-config")
def bonus_config_save(payload: dict = Body(...)):
    """
    P1.4.4: Guarda nueva version de configuracion de bonos.
    Desactiva configs activas anteriores e inserta las nuevas filas.
    Valida bonus_type, trips_min > 0, bonus_pct >= 0, bonus_amount >= 0.
    """
    park_id = payload.get("park_id", PARK_ID)
    return save_bonus_config(park_id=park_id, payload=payload)


@router.post("/simulator/bonus-config/reset")
def bonus_config_reset(payload: dict = Body(...)):
    """
    P1.4.4: Restaura defaults como nueva version activa.
    No borra historico.
    """
    park_id = payload.get("park_id", PARK_ID)
    config_name = payload.get("config_name", "default")
    return reset_bonus_config_to_defaults(park_id=park_id, config_name=config_name)


@router.get("/simulator/baseline")
def simulator_baseline(
    park_id: str = Query(default=PARK_ID, description="Park ID"),
):
    """
    P1.4.5A: Escenario baseline "OPERACION REAL" calculado desde
    datos operativos reales (module_weekly_billing, trips_2026,
    module_calculated_shifts, bonus config persistida).
    """
    return get_baseline_scenario(park_id=park_id)


@router.get("/simulator/scenarios")
def scenarios_list(
    park_id: str = Query(default=PARK_ID, description="Park ID"),
    include_archived: bool = Query(default=False, description="Include archived scenarios"),
):
    """
    P1.4.5A: Lista escenarios guardados del Simulator.
    """
    return list_scenarios(park_id=park_id, include_archived=include_archived)


@router.post("/simulator/scenarios")
def scenarios_save(payload: dict = Body(...)):
    """
    P1.4.5A: Guarda un nuevo escenario.
    Recibe: scenario_name, scenario_type, inputs, outputs, calculation_trace, etc.
    """
    park_id = payload.get("park_id", PARK_ID)
    return save_scenario(park_id=park_id, payload=payload)


@router.patch("/simulator/scenarios/{scenario_id}")
def scenarios_update(scenario_id: int, payload: dict = Body(...)):
    """
    P1.4.5A: Actualiza campos de un escenario (nombre, favorito, archivado, etc.).
    Baselines solo permiten modificar nombre e is_favorite.
    """
    return update_scenario(scenario_id=scenario_id, payload=payload)


@router.post("/simulator/scenarios/{scenario_id}/duplicate")
def scenarios_duplicate(scenario_id: int, payload: dict = Body(...)):
    """
    P1.4.5A: Duplica un escenario existente.
    """
    new_name = payload.get("scenario_name")
    return duplicate_scenario(scenario_id=scenario_id, new_name=new_name)


@router.post("/simulator/scenarios/{scenario_id}/archive")
def scenarios_archive(scenario_id: int):
    """
    P1.4.5A: Archiva un escenario (soft-delete).
    """
    return archive_scenario(scenario_id=scenario_id)


@router.get("/simulator/operational-baseline")
def simulator_operational_baseline(
    park_id: str = Query(default=PARK_ID, description="Park ID para baseline operativo"),
):
    """
    P2.2.1: Baseline operativo con datos reales de produccion, costos y KPIs.
    Devuelve inputs con referencia operativa real, financial_summary y missing_inputs.
    """
    return get_operational_baseline(park_id=park_id)


@router.get("/simulator/operational-references")
def simulator_operational_references(
    park_id: str = Query(default=PARK_ID, description="Park ID"),
):
    """
    P2.2.1: Referencias operativas reales para cada input del Simulator.
    Devuelve value, source, confidence, period para cada input editable.
    """
    return get_operational_references_real(park_id=park_id)


@router.get("/kpi-explainability")
def kpi_explainability(
    park_id: str = Query(default=PARK_ID, description="Park ID"),
):
    """
    P2.2.1: Explicacion de KPIs financieros clave.
    Incluye formula, componentes, fuentes y confianza para cada KPI ejecutivo.
    """
    return get_kpi_explainability(park_id=park_id)


@router.get("/driver-drill")
def driver_drill(
    park_id: str = Query(default=PARK_ID, description="Park ID"),
    driver_id: str = Query(..., description="Driver ID"),
):
    """
    P2.2.2: Drill-down por conductor.
    Devuelve desglose completo de ingresos, costos, pago y resultado por conductor.
    """
    return get_driver_drill(park_id=park_id, driver_id=driver_id)


@router.get("/vehicle-drill")
def vehicle_drill(
    park_id: str = Query(default=PARK_ID, description="Park ID"),
    plate: str = Query(..., description="Placa del vehiculo"),
):
    """
    P2.2.2: Drill-down por vehiculo.
    Devuelve desglose completo de ingresos, costos, pago y resultado por placa.
    """
    return get_vehicle_drill(park_id=park_id, plate=plate)
