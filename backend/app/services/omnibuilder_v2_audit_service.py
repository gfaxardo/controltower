"""
OV2-A — OMNIBUILDER V2 AUDIT SERVICE (PLACEHOLDER)

Fase: OV2-A — Blindaje Lógico
Estado: SOLO DOCUMENTACIÓN — No implementar hasta OV2-B

Responsabilidades:
    - Trazabilidad de métricas (lineage RAW → FACT → SERVING → API → UI)
    - Matriz de frescura (última fecha de dato por grain × metric)
    - Matriz de cobertura (coverage_pct por grain × metric × country)
    - Validación de contrato de celda canónica
    - Trazabilidad de source de cada celda
"""


class OmnibuilderV2AuditService:
    """
    PLACEHOLDER — OV2-B
    
    Servicio de auditoría y trazabilidad para OV2.
    No implementar hasta que OMNI-P0 cierre con GO real.
    """

    async def get_metric_lineage(self, metric_id: str) -> dict:
        """
        Devuelve árbol de dependencias RAW → FACT → SERVING → API para una métrica.
        
        Args:
            metric_id: trips_completed | revenue_yego_net | active_drivers | ...
        
        Returns:
            {
                "metric_id": "trips_completed",
                "lineage": [
                    {"layer": "RAW", "source": "public.trips_2026", "grain": "trip"},
                    {"layer": "FACT_DAY", "source": "ops.real_business_slice_day_fact", "grain": "day"},
                    ...
                ]
            }
        """
        raise NotImplementedError("OV2-B")

    async def get_freshness_matrix(self) -> dict:
        """
        Devuelve última fecha de dato por grain × metric.
        """
        raise NotImplementedError("OV2-B")

    async def get_coverage_matrix(self) -> dict:
        """
        Devuelve coverage_pct por grain × metric × country.
        """
        raise NotImplementedError("OV2-B")

    async def get_active_risks(self) -> list:
        """
        Devuelve riesgos del risk register con status actual.
        """
        raise NotImplementedError("OV2-B")

    async def validate_cell_contract(self, cell_data: dict) -> dict:
        """
        Valida que una celda cumpla el contrato canónico OV2.
        
        Args:
            cell_data: Datos de celda a validar.
        
        Returns:
            {"valid": True/False, "violations": [...]}
        """
        raise NotImplementedError("OV2-B")

    async def trace_cell_source(
        self, country: str, city: str, slice: str, period: str, metric: str
    ) -> dict:
        """
        Trazabilidad completa de una celda específica.
        """
        raise NotImplementedError("OV2-B")
