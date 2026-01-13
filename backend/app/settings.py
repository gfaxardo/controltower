import os
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List

class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "yego_integral"
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    
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
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:CORS_ORIGINS","message":"Convirtiendo CORS_ORIGINS_STR a lista","data":{"cors_origins_str":self.CORS_ORIGINS_STR},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",") if origin.strip()]
    
    ENVIRONMENT: str = "dev"
    
    DATABASE_URL: str = ""

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True
    }

# #region agent log
import json
LOG_PATH = r"c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\.cursor\debug.log"
try:
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:Settings","message":"Inicializando Settings","data":{"env_file_exists":os.path.exists(".env")},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
        f.write("\n")
except: pass
# #endregion

# #region agent log
try:
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:before_Settings","message":"Antes de crear Settings","data":{},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
        f.write("\n")
except: pass
# #endregion

try:
    settings = Settings()
    # #region agent log
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:settings_created","message":"Settings creado exitosamente","data":{"cors_origins_str":settings.CORS_ORIGINS_STR},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    
    # #region agent log
    try:
        cors_origins_list = settings.CORS_ORIGINS
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:settings","message":"Settings inicializado","data":{"cors_origins":cors_origins_list,"cors_origins_type":type(cors_origins_list).__name__},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:settings_error","message":"Error al acceder CORS_ORIGINS","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    # #endregion
except Exception as e:
    # #region agent log
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H3","location":"settings.py:Settings_exception","message":"Excepción al crear Settings","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(__import__('time').time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    raise
# #endregion

