from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Literal
from datetime import datetime, date
from uuid import UUID

class PlanUploadResponse(BaseModel):
    rows_valid: int
    rows_out_of_universe: int
    missing_combos_count: int
    source_file_name: str
    uploaded_at: datetime
    file_hash: str
    rows_loaded: Optional[int] = None
    preview_out_of_universe_top20: Optional[List[Dict]] = None

class MonthlySummaryPoint(BaseModel):
    period: str
    trips_plan: Optional[float] = None
    revenue_plan: Optional[float] = None

class PlanMonthlySummaryResponse(BaseModel):
    data: List[MonthlySummaryPoint]
    total_periods: int

class RealMonthlySummaryPoint(BaseModel):
    period: str
    trips_real: Optional[float] = None
    revenue_real: Optional[float] = None

class RealMonthlySummaryResponse(BaseModel):
    data: List[RealMonthlySummaryPoint]
    total_periods: int

class CoreMonthlySummaryPoint(BaseModel):
    period: str
    trips_plan: Optional[float] = None
    revenue_plan: Optional[float] = None
    trips_real: Optional[float] = None
    revenue_real: Optional[float] = None
    delta_trips_abs: Optional[float] = None
    delta_trips_pct: Optional[float] = None
    delta_revenue_abs: Optional[float] = None
    delta_revenue_pct: Optional[float] = None
    comparison_status: str

class CoreMonthlySummaryResponse(BaseModel):
    data: List[CoreMonthlySummaryPoint]
    total_periods: int

class OpsUniversePoint(BaseModel):
    country: str
    city: str
    line_of_business: str

class OpsUniverseResponse(BaseModel):
    data: List[OpsUniversePoint]
    total_combinations: int


# Schemas para Fase 2B - Acciones
class Phase2BActionCreate(BaseModel):
    week_start: date
    country: str
    city_norm: Optional[str] = None
    lob_base: Optional[str] = None
    segment: Optional[str] = None
    alert_type: str
    root_cause: str
    action_type: str
    action_description: str
    owner_role: str
    owner_user_id: Optional[UUID] = None
    due_date: date


class Phase2BActionUpdate(BaseModel):
    status: Optional[Literal['OPEN', 'IN_PROGRESS', 'DONE', 'MISSED']] = None
    action_description: Optional[str] = None


class Phase2BActionResponse(BaseModel):
    phase2b_action_id: int
    week_start: date
    country: str
    city_norm: Optional[str] = None
    lob_base: Optional[str] = None
    segment: Optional[str] = None
    alert_type: str
    root_cause: str
    action_type: str
    action_description: str
    owner_role: str
    owner_user_id: Optional[UUID] = None
    due_date: date
    status: str
    created_at: datetime
    updated_at: datetime


class Phase2BActionsListResponse(BaseModel):
    data: List[Phase2BActionResponse]
    total: int
