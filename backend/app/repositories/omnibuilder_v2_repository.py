"""
OV2-A — OMNIBUILDER V2 REPOSITORY (PLACEHOLDER)

Fase: OV2-A — Blindaje Lógico
Estado: SOLO DOCUMENTACIÓN — No implementar hasta OV2-B

Responsabilidades:
    - Queries SQL a la capa v2.* de serving facts
    - Acceso a v2.business_slice_{grain}_serving
    - Acceso a v2.projection_{grain}_fact
    - Queries de auditoría (lineage, freshness, coverage)
"""


class OmnibuilderV2Repository:
    """
    PLACEHOLDER — OV2-B
    
    Repositorio de datos para la capa v2.* de serving facts.
    No implementar hasta que OMNI-P0 cierre con GO real.
    """

    async def get_serving_matrix(self, grain: str, filters: dict) -> list:
        """
        Query a v2.business_slice_{grain}_serving con filtros aplicados.
        
        Args:
            grain: day | week | month
            filters: country, city, business_slice, year, month, etc.
        """
        raise NotImplementedError("OV2-B")

    async def get_cell(
        self, grain: str, country: str, city: str, slice_name: str, period: str
    ) -> dict:
        """
        Query de celda individual desde serving view.
        """
        raise NotImplementedError("OV2-B")

    async def get_freshness_all(self) -> list:
        """
        Query de frescura de todos los serving facts v2.
        """
        raise NotImplementedError("OV2-B")

    async def get_coverage_matrix(self) -> list:
        """
        Matriz de cobertura grain × metric × country.
        """
        raise NotImplementedError("OV2-B")

    async def get_lineage(self, metric_id: str) -> list:
        """
        CTE recursivo de lineage de métrica.
        """
        raise NotImplementedError("OV2-B")

    async def get_period_status(self, country: str, period: str) -> dict:
        """
        Estado de cierre de período (CLOSED/PARTIAL/CURRENT/FUTURE).
        """
        raise NotImplementedError("OV2-B")
