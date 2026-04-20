import os
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List

def ensure_utf8(value: str) -> str:
    """Asegura que un string esté en UTF-8, convirtiendo desde otras codificaciones si es necesario."""
    if not value:
        return value
    if isinstance(value, bytes):
        # Intentar decodificar desde diferentes codificaciones
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                return value.decode(encoding)
            except (UnicodeDecodeError, AttributeError):
                continue
        # Fallback: reemplazar caracteres inválidos
        return value.decode('utf-8', errors='replace')
    # Si ya es string, verificar que se pueda codificar en UTF-8
    try:
        value.encode('utf-8')
        return value
    except UnicodeEncodeError:
        # Intentar convertir desde otras codificaciones
        for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
            try:
                return value.encode(encoding).decode('utf-8')
            except:
                continue
        # Fallback: reemplazar caracteres problemáticos
        return value.encode('utf-8', errors='replace').decode('utf-8')

class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "yego_integral"
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    
    @field_validator('DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME', mode='before')
    @classmethod
    def validate_encoding(cls, v):
        """Valida y convierte a UTF-8."""
        if v and isinstance(v, str):
            return ensure_utf8(v)
        return v
    
    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    
    CORS_ORIGINS_STR: str = Field(
        default=(
            "http://localhost:5173,http://localhost:3000,"
            "http://162.55.214.109,https://162.55.214.109,"
            "http://5.161.86.63,https://5.161.86.63"
        ),
        alias="CORS_ORIGINS",
    )
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        # #region agent log
        import json
        LOG_PATH = r"c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\.cursor\debug.log"
        try:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:CORS_ORIGINS","message":"Convirtiendo CORS_ORIGINS_STR a lista","data":{"cors_origins_str":self.CORS_ORIGINS_STR},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",") if origin.strip()]
    
    ENVIRONMENT: str = "dev"
    
    DATABASE_URL: str = ""

    # Destino del login (solo servidor; el front usa /api/auth/login relativo).
    INTEGRAL_AUTH_LOGIN_URL: str = "https://api-int.yego.pro/api/auth/login"

    # Fuente REAL mensual: True = cadena canónica (real_drill_dim_fact); False = legacy (mv_real_trips_monthly).
    # New consumers must use canonical only. Ver docs/REAL_CANONICAL_CHAIN.md y CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md.
    USE_CANONICAL_REAL_MONTHLY: bool = Field(default=False, description="Usar real mensual desde cadena hourly-first")

    # Plan vs Real: por defecto usar canónica solo si parity es MATCH o MINOR_DIFF (leído de ops.plan_vs_real_parity_audit).
    # Si False, siempre legacy salvo ?source=canonical. Si True, usar canónica cuando parity lo permita.
    USE_CANONICAL_PLAN_VS_REAL_DEFAULT: bool = Field(default=False, description="Usar real canónica en Plan vs Real cuando parity sea OK")

    # Real LOB modo incremental: ventana reciente (días) para migración/refresh inicial.
    # Backfill histórico: python -m scripts.backfill_real_lob_mvs --from YYYY-MM-01 --to YYYY-MM-01
    REAL_LOB_RECENT_DAYS: int = 90

    # ── Omniview Matrix: refresh automático day_fact + week_fact (loader incremental) ──
    OMNIVIEW_REAL_REFRESH_ENABLED: bool = Field(
        default=False,
        description="Si True, APScheduler ejecuta recarga day/week fact periódicamente (mes actual + anterior).",
    )
    OMNIVIEW_REAL_REFRESH_INTERVAL_MINUTES: int = Field(
        default=60,
        ge=15,
        le=1440,
        description="Intervalo del job de refresh (mín. 15 min).",
    )
    OMNIVIEW_REAL_REFRESH_TIMEOUT_MS: int = Field(
        default=1_800_000,
        description="statement_timeout para el job (default 30 min).",
    )
    OMNIVIEW_REAL_FRESH_LAG_STALE_DAYS: int = Field(
        default=1,
        ge=0,
        description="Lag días MAX(trip_date) vs hoy para marcar stale en /real-freshness.",
    )
    OMNIVIEW_REAL_FRESH_LAG_CRITICAL_DAYS: int = Field(
        default=2,
        ge=0,
        description="Lag días para marcar critical.",
    )
    OMNIVIEW_UPSTREAM_MODE: str = Field(
        default="table",
        description="Upstream para freshness: 'table' (OMNIVIEW_UPSTREAM_TRIPS_TABLE) o 'canon' (ops.v_trips_real_canon).",
    )
    OMNIVIEW_UPSTREAM_TRIPS_TABLE: str = Field(
        default="public.trips_2026",
        description="schema.tabla para MAX(fecha) en modo table.",
    )
    OMNIVIEW_UPSTREAM_DATE_COLUMN: str = Field(
        default="fecha_inicio_viaje",
        description="Columna de fecha en la tabla upstream (solo identificadores seguros).",
    )
    OMNIVIEW_UPSTREAM_RECENT_DAYS: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Ventana (días) para row_count_recent en upstream.",
    )
    OMNIVIEW_REAL_REFRESH_MIN_INTERVAL_MINUTES: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="No ejecutar refresh si hubo una corrida hace menos de estos minutos (cooldown).",
    )
    OMNIVIEW_REAL_WATCHDOG_ENABLED: bool = Field(
        default=False,
        description="Si True, job watchdog + auto-recovery (requiere scheduler en main).",
    )
    OMNIVIEW_REAL_WATCHDOG_INTERVAL_MINUTES: int = Field(
        default=15,
        ge=5,
        le=1440,
        description="Intervalo del watchdog.",
    )
    REAL_FRESHNESS_ALERT_WEBHOOK: str = Field(
        default="",
        description="URL opcional POST JSON en alertas del watchdog (vacío = desactivado).",
    )

    # ── Projection Integrity Engine (Omniview proyección derivada mensual) ──
    PROJECTION_SMOOTHING_ALPHA_WEEK: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Blend curva histórica vs uniforme semanal (week_share_of_month).",
    )
    PROJECTION_SMOOTHING_ALPHA_DAY: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Blend curva histórica vs progreso lineal por día (ratio acumulado mensual y share diario).",
    )
    PROJECTION_CONSERVATION_TOLERANCE_PCT: float = Field(
        default=0.1,
        ge=0.0,
        description="Tolerancia %% para drift de conservación sin ajuste (además de drift_abs<=1).",
    )

    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True
    }

# #region agent log
import json
LOG_PATH = r"c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\.cursor\debug.log"
try:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:Settings","message":"Inicializando Settings","data":{"env_file_exists":os.path.exists(".env")},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
        f.write("\n")
except: pass
# #endregion

# #region agent log
try:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:before_Settings","message":"Antes de crear Settings","data":{},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
        f.write("\n")
except: pass
# #endregion

try:
    settings = Settings()
    # #region agent log
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:settings_created","message":"Settings creado exitosamente","data":{"cors_origins_str":settings.CORS_ORIGINS_STR},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    
    # #region agent log
    try:
        cors_origins_list = settings.CORS_ORIGINS
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:settings","message":"Settings inicializado","data":{"cors_origins":cors_origins_list,"cors_origins_type":type(cors_origins_list).__name__},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        try:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:settings_error","message":"Error al acceder CORS_ORIGINS","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
    # #endregion
except Exception as e:
    # #region agent log
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:Settings_exception","message":"Excepción al crear Settings","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    raise
# #endregion

