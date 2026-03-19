"""
Source of Truth Registry — Registro central de qué fuente manda por dominio/vista.
Ninguna vista nueva puede salir a UI sin estar registrada aquí.
Legacy puede existir pero debe estar marcado.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

# --- Tipado del registro por dominio ---


class DomainEntry(TypedDict, total=False):
    """Entrada por dominio: primary manda; secondary/legacy son fallback o referencia."""
    primary: str
    secondary: List[str]
    legacy: List[str]
    grain: str
    canonical_chain: bool
    source_mode: str  # canonical | migrating | legacy | under_review | source_incomplete
    freshness_dataset: Optional[str]  # nombre en data_freshness_audit si aplica
    parity_audit_applies: bool  # si plan_vs_real parity aplica
    notes: str


# --- Registry: una sola fuente de verdad por dominio ---

SOURCE_OF_TRUTH: Dict[str, DomainEntry] = {
    "real_lob": {
        "primary": "ops.real_drill_dim_fact",
        "secondary": ["ops.mv_real_drill_dim_agg", "ops.real_rollup_day_fact", "ops.mv_real_lob_day_v2"],
        "legacy": ["ops.mv_real_trips_by_lob_day", "ops.mv_real_rollup_day"],
        "grain": "daily",
        "canonical_chain": True,
        "source_mode": "canonical",
        "freshness_dataset": "real_lob_drill",
        "parity_audit_applies": False,
        "notes": "Drill y Real diario: cadena hourly-first canónica (real_drill_dim_fact, rollup desde day_v2).",
    },
    "resumen": {
        "primary": "ops.mv_real_monthly_canonical_hist",
        "secondary": [],
        "legacy": ["ops.mv_real_trips_monthly"],
        "grain": "monthly",
        "canonical_chain": True,
        "source_mode": "canonical",
        "freshness_dataset": None,
        "parity_audit_applies": False,
        "notes": "Resumen mensual histórico canónico; KPICards consumen canonical vía GET /ops/real/monthly?source=canonical.",
    },
    "plan_vs_real": {
        "primary": "ops.v_plan_vs_real_realkey_canonical",
        "secondary": ["ops.v_plan_vs_real_realkey_final"],
        "legacy": ["ops.v_plan_vs_real_realkey_final", "ops.mv_real_trips_monthly"],
        "grain": "monthly",
        "canonical_chain": True,
        "source_mode": "migrating",
        "freshness_dataset": None,
        "parity_audit_applies": True,
        "notes": "Migrando a canónica; se usa canonical solo si parity MATCH/MINOR (ops.plan_vs_real_parity_audit).",
    },
    "real_vs_projection": {
        "primary": "ops.v_real_metrics_monthly",
        "secondary": [],
        "legacy": ["ops.mv_real_trips_monthly"],
        "grain": "monthly",
        "canonical_chain": False,
        "source_mode": "source_incomplete",
        "freshness_dataset": "real_lob",
        "parity_audit_applies": False,
        "notes": "Real desde legacy (v_real_metrics_monthly → mv_real_trips_monthly). Vista temporalmente limitada.",
    },
    "supply": {
        "primary": "ops.mv_supply_segments_weekly",
        "secondary": ["ops.mv_supply_weekly", "ops.mv_supply_monthly"],
        "legacy": [],
        "grain": "weekly",
        "canonical_chain": True,
        "source_mode": "canonical",
        "freshness_dataset": None,
        "parity_audit_applies": False,
        "notes": "Supply de conductores; freshness vía get_supply_freshness y ops.supply_refresh_log.",
    },
    "driver_lifecycle": {
        "primary": "ops.mv_driver_lifecycle_base",
        "secondary": ["ops.mv_driver_lifecycle_weekly_kpis", "ops.mv_driver_lifecycle_monthly_kpis"],
        "legacy": ["ops.mv_driver_weekly_stats", "ops.mv_driver_monthly_stats"],
        "grain": "weekly",
        "canonical_chain": True,
        "source_mode": "canonical",
        "freshness_dataset": None,
        "parity_audit_applies": False,
        "notes": "Ciclo de vida por park; freshness = MAX(last_completed_ts) en mv_driver_lifecycle_base.",
    },
    "behavioral_alerts": {
        "primary": "ops.v_driver_behavior_alerts_weekly",
        "secondary": ["ops.mv_driver_behavior_alerts_weekly"],
        "legacy": [],
        "grain": "weekly",
        "canonical_chain": False,
        "source_mode": "under_review",
        "freshness_dataset": None,
        "parity_audit_applies": False,
        "notes": "Alertas de conducta; en revisión. Validar estabilidad en runtime.",
    },
    "leakage": {
        "primary": "ops.v_fleet_leakage_snapshot",
        "secondary": ["ops.mv_driver_segments_weekly", "ops.v_driver_last_trip"],
        "legacy": [],
        "grain": "weekly",
        "canonical_chain": False,
        "source_mode": "under_review",
        "freshness_dataset": None,
        "parity_audit_applies": False,
        "notes": "Fuga de flota; en revisión.",
    },
    "real_margin_quality": {
        "primary": "ops.v_real_trip_fact_v2",
        "secondary": [],
        "legacy": [],
        "grain": "daily",
        "canonical_chain": True,
        "source_mode": "canonical",
        "freshness_dataset": "real_operational",
        "parity_audit_applies": False,
        "notes": "Margin quality desde cadena hourly-first (v_real_trip_fact_v2).",
    },
}

# Vistas que exponen Data Trust en UI (subconjunto del registry)
DATA_TRUST_VIEWS = ("real_lob", "resumen", "plan_vs_real", "supply", "driver_lifecycle")

# Todas las vistas registradas (para summary/observabilidad)
REGISTERED_VIEWS = tuple(SOURCE_OF_TRUTH.keys())


def get_registry_entry(view_name: str) -> Optional[DomainEntry]:
    """Devuelve la entrada del registro para una vista; None si no existe."""
    return SOURCE_OF_TRUTH.get(view_name.strip().lower())


def get_primary_source(view_name: str) -> Optional[str]:
    """Fuente primaria que manda hoy para esta vista."""
    entry = get_registry_entry(view_name)
    return entry.get("primary") if entry else None


def get_source_mode(view_name: str) -> str:
    """canonical | migrating | legacy | under_review | source_incomplete."""
    entry = get_registry_entry(view_name)
    if not entry:
        return "unknown"
    return entry.get("source_mode") or "unknown"
