"""
OV2-A — OMNIBUILDER V2 REGISTRY SERVICE (PLACEHOLDER)

Fase: OV2-A — Blindaje Lógico
Estado: SOLO DOCUMENTACIÓN — No implementar hasta OV2-B

Responsabilidades:
    - Catálogo canónico de métricas (metric_id, nombre, fórmula, fuente, grain, aggregation)
    - Catálogo de fuentes de datos (source_id, tipo, frescura, dependencias)
    - Validación de registros contra serving facts reales
"""


class OmnibuilderV2RegistryService:
    """
    PLACEHOLDER — OV2-B
    
    Servicio de registro canónico de métricas y fuentes para OV2.
    No implementar hasta que OMNI-P0 cierre con GO real.
    """

    CANONICAL_METRICS = {
        "trips_completed": {
            "label": "Viajes",
            "unit": "number",
            "aggregation": "additive",
            "source_fact": "ops.real_business_slice_{grain}_fact",
            "formula": "SUM(trips_completed) FILTER (WHERE completed_flag)",
            "grains": ["day", "week", "month"],
            "cross_grain_comparable": True,
        },
        "revenue_yego_net": {
            "label": "Revenue",
            "unit": "currency",
            "aggregation": "additive",
            "source_fact": "ops.real_business_slice_{grain}_fact",
            "formula": "SUM(ABS(NULLIF(comision_empresa_asociada, 0)))",
            "grains": ["day", "week", "month"],
            "cross_grain_comparable": True,
            "has_proxy_fallback": True,
        },
        "active_drivers": {
            "label": "Conductores",
            "unit": "number",
            "aggregation": "semi_additive_distinct",
            "source_fact": "ops.real_business_slice_{grain}_fact",
            "formula": "COUNT(DISTINCT driver_uuid)",
            "grains": ["day", "week", "month"],
            "cross_grain_comparable": False,
        },
        "avg_ticket": {
            "label": "Ticket Promedio",
            "unit": "currency",
            "aggregation": "non_additive_ratio",
            "source_fact": "ops.real_business_slice_{grain}_fact",
            "formula": "SUM(revenue) / NULLIF(SUM(trips), 0)",
            "grains": ["day", "week", "month"],
            "cross_grain_comparable": True,
            "note": "Debe precalcularse en fact table en OV2-B",
        },
        "trips_per_driver": {
            "label": "TPD",
            "unit": "number",
            "aggregation": "derived_ratio",
            "source_fact": "ops.real_business_slice_{grain}_fact",
            "formula": "trips_completed / NULLIF(active_drivers, 0)",
            "grains": ["day", "week", "month"],
            "cross_grain_comparable": False,
            "note": "Debe precalcularse en fact table en OV2-B",
        },
        "cancel_rate_pct": {
            "label": "Cancel %",
            "unit": "percentage",
            "aggregation": "non_additive_ratio",
            "source_fact": "ops.real_business_slice_{grain}_fact",
            "formula": "SUM(cancelled) / NULLIF(SUM(completed) + SUM(cancelled), 0) * 100",
            "grains": ["day", "week", "month"],
            "cross_grain_comparable": True,
            "note": "Debe precalcularse en fact table en OV2-B",
        },
        "commission_pct": {
            "label": "Comm %",
            "unit": "percentage",
            "aggregation": "non_additive_ratio",
            "source_fact": "ops.real_business_slice_{grain}_fact",
            "formula": "SUM(revenue) / NULLIF(SUM(total_fare), 0) * 100",
            "grains": ["day", "week", "month"],
            "cross_grain_comparable": True,
            "note": "Debe precalcularse en fact table en OV2-B. Depende de revenue proxy fallback.",
        },
    }

    CANONICAL_SOURCES = {
        "business_slice_month": {
            "entity": "ops.real_business_slice_month_fact",
            "type": "FACT_TABLE",
            "grain": "monthly",
            "serving_view": "v2.business_slice_month_serving",
            "depends_on": ["public.trips_2026", "ops.v_real_trips_enriched_base"],
        },
        "business_slice_week": {
            "entity": "ops.real_business_slice_week_fact",
            "type": "FACT_TABLE",
            "grain": "weekly",
            "serving_view": "v2.business_slice_week_serving",
            "depends_on": ["public.trips_2026", "ops.v_real_trips_enriched_base"],
        },
        "business_slice_day": {
            "entity": "ops.real_business_slice_day_fact",
            "type": "FACT_TABLE",
            "grain": "daily",
            "serving_view": "v2.business_slice_day_serving",
            "depends_on": ["public.trips_2026", "ops.v_real_trips_enriched_base"],
        },
    }

    async def get_metric_registry(self) -> dict:
        """Devuelve catálogo completo de métricas canónicas."""
        raise NotImplementedError("OV2-B")

    async def get_metric_by_id(self, metric_id: str) -> dict:
        """Devuelve ficha completa de una métrica."""
        raise NotImplementedError("OV2-B")

    async def get_source_registry(self) -> dict:
        """Devuelve catálogo completo de fuentes de datos."""
        raise NotImplementedError("OV2-B")

    async def register_metric(self, metric_def: dict) -> dict:
        """Registra una nueva métrica en el catálogo."""
        raise NotImplementedError("OV2-B")

    async def register_source(self, source_def: dict) -> dict:
        """Registra una nueva fuente de datos."""
        raise NotImplementedError("OV2-B")
