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
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ORIGINS"
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

    # Real LOB modo incremental: ventana reciente (días) para migración/refresh inicial.
    # Backfill histórico: python -m scripts.backfill_real_lob_mvs --from YYYY-MM-01 --to YYYY-MM-01
    REAL_LOB_RECENT_DAYS: int = 90

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

