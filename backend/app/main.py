from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.settings import settings
from app.db.connection import init_db_pool, create_plan_schema, create_ingestion_status_schema
from app.db.schema_verify import verify_schema, inspect_real_columns
from app.routers import plan, real, core, ops, health, ingestion, phase2b, phase2c, driver_lifecycle, controltower
import logging
import time
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YEGO Control Tower API", version="2.0.0")

# Request logging: path, duration, status, optional query params for /ops/ (performance baseline)
def _ops_query_params_snippet(request: Request) -> str:
    try:
        q = request.query_params
        if not q:
            return ""
        # Log only a few key params to detect duplicate calls (no PII)
        parts = []
        for k in ("period", "desglose", "segmento", "park_id", "recent_weeks", "baseline_weeks", "limit", "offset"):
            v = q.get(k)
            if v is not None:
                parts.append(f"{k}={v}")
        if not parts:
            return ""
        return " " + " ".join(parts[:6])
    except Exception:
        return ""


@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000)
    path = request.url.path
    extra = ""
    if path.startswith("/ops/") and request.method == "GET":
        extra = _ops_query_params_snippet(request)
    logger.info(
        "REQ %s %s %s %s %sms%s",
        request_id,
        request.method,
        path,
        response.status_code,
        duration_ms,
        extra,
        extra={"duration_ms": duration_ms, "request_id": request_id},
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan.router)
app.include_router(real.router)
app.include_router(core.router)
app.include_router(ops.router)
app.include_router(phase2b.router)
app.include_router(phase2c.router)
app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(driver_lifecycle.router)
app.include_router(controltower.router)

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando YEGO Control Tower API...")
    try:
        init_db_pool()
        logger.info("Pool de conexiones inicializado")
        
        create_plan_schema()
        logger.info("Esquema plan creado/verificado")
        
        create_ingestion_status_schema()
        logger.info("Esquema ingestion_status creado/verificado")
        
        table_structures = verify_schema()
        logger.info("Estructuras de tablas verificadas")
        
        inspection_results = inspect_real_columns()
        logger.info("Inspección de columnas reales completada")
        
    except Exception as e:
        logger.error(f"Error en startup: {e}")
        raise

@app.get("/")
async def root():
    return {
        "message": "YEGO Control Tower API - Fase 2A",
        "version": "2.0.0",
        "docs": "/docs"
    }
