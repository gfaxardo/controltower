from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.settings import settings
from app.startup_checks import run_startup_checks
from app.startup_state import set_startup_report
from app.routers import auth, plan, real, core, ops, health, ingestion, phase2b, phase2c, driver_lifecycle, driver_lifecycle_diagnostic, driver_behavior_benchmarking, controltower, observability, real_vs_projection, diagnostics, ops_refresh, fraud, behavioral_pattern_diagnosis, behavioral_mvp, operational_behavioral_intelligence, recoverability_intelligence, yango_loyalty, drivers, yego_pro_profitability, yego_lima_growth_lab, yego_lima_growth_control_loop, yego_lima_executive, yego_lima_pipeline
import logging
import time
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_omniview_real_refresh_scheduler = None

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

app.include_router(auth.router)
app.include_router(plan.router)
app.include_router(real.router)
app.include_router(core.router)
app.include_router(ops.router)
app.include_router(phase2b.router)
app.include_router(phase2c.router)
app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(driver_lifecycle.router)
app.include_router(driver_lifecycle_diagnostic.router)
app.include_router(driver_behavior_benchmarking.router)
app.include_router(drivers.router)
app.include_router(controltower.router)
app.include_router(observability.router, prefix="/ops")
app.include_router(real_vs_projection.router, prefix="/ops")
app.include_router(diagnostics.router)
app.include_router(ops_refresh.router, prefix="/ops")
app.include_router(fraud.router)
app.include_router(behavioral_pattern_diagnosis.router)
app.include_router(behavioral_mvp.router)
app.include_router(operational_behavioral_intelligence.router)
app.include_router(recoverability_intelligence.router)
app.include_router(yango_loyalty.router)
app.include_router(yego_pro_profitability.router)

app.include_router(yego_lima_growth_lab.router)

app.include_router(yego_lima_growth_control_loop.router)

app.include_router(yego_lima_executive.router)
app.include_router(yego_lima_pipeline.router)

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando YEGO Control Tower API...")
    try:
        report = run_startup_checks()
        set_startup_report(report)
        logger.info(
            "Startup: overall=%s checks=%s",
            report.get("overall"),
            len(report.get("checks") or []),
        )
        if report.get("overall") == "blocked":
            detail = next(
                (c.get("detail") for c in (report.get("checks") or []) if c.get("status") == "failed"),
                "db_pool u operación bloqueante falló",
            )
            raise RuntimeError(f"Startup bloqueado: {detail}")
    except ValueError:
        # verify_schema en dev: columnas críticas faltantes
        raise
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Error en startup: {e}")
        raise

    global _omniview_real_refresh_scheduler
    from app.services.scheduler_status_service import (
        set_scheduler_active,
        set_scheduler_disabled,
        set_scheduler_missing_dependency,
        set_scheduler_error,
        APSCHEDULER_AVAILABLE,
    )

    if not APSCHEDULER_AVAILABLE:
        set_scheduler_missing_dependency("apscheduler not installed in environment")
        logger.warning(
            "APScheduler NO disponible: apscheduler no instalado en el entorno. "
            "Ejecutar: pip install apscheduler>=3.10.0"
        )

    if settings.OMNIVIEW_REAL_REFRESH_ENABLED or settings.OMNIVIEW_REAL_WATCHDOG_ENABLED:
        from app.services.refresh_control_service import is_scheduler_enabled

        if not is_scheduler_enabled():
            set_scheduler_disabled("CT_SCHEDULER_ENABLED=false")
            logger.info(
                "APScheduler NO iniciado: CT_SCHEDULER_ENABLED=false en entorno %s.",
                getattr(settings, "ENVIRONMENT", "unknown"),
            )
        elif not APSCHEDULER_AVAILABLE:
            pass
        else:
            try:
                from apscheduler.schedulers.background import BackgroundScheduler

                from app.omniview_real_scheduler_info import attach_omniview_scheduler
                from app.services.business_slice_real_refresh_job import (
                    run_business_slice_real_refresh_job_safe,
                )
                from app.services.real_data_watchdog_service import run_real_data_watchdog

                _omniview_real_refresh_scheduler = BackgroundScheduler(daemon=True)
                jobs_registered = []

                # FASE 1H.1 — Serving fact refresh diario (05:00 UTC)
                try:
                    from app.services.serving_refresh_scheduler import scheduled_daily_refresh
                    _omniview_real_refresh_scheduler.add_job(
                        scheduled_daily_refresh,
                        "cron",
                        hour=5,
                        minute=0,
                        id="serving_fact_daily_refresh",
                        replace_existing=True,
                        max_instances=1,
                        coalesce=True,
                        misfire_grace_time=1800,
                    )
                    jobs_registered.append("serving_fact_daily_refresh")
                    logger.info("Serving fact refresh programado: 05:00 diario (daily+weekly+monthly).")
                except Exception as e:
                    logger.warning("No se pudo registrar serving refresh scheduler: %s", e)

                if settings.OMNIVIEW_REAL_REFRESH_ENABLED:
                    _omniview_real_refresh_scheduler.add_job(
                        run_business_slice_real_refresh_job_safe,
                        "cron",
                        hour=settings.OMNIVIEW_REAL_REFRESH_HOUR,
                        minute=settings.OMNIVIEW_REAL_REFRESH_MINUTE,
                        id="omniview_business_slice_real_refresh",
                        replace_existing=True,
                        max_instances=1,
                        coalesce=True,
                        misfire_grace_time=600,
                    )
                    jobs_registered.append("omniview_business_slice_real_refresh")
                    logger.info(
                        "Omniview REAL refresh programado: %02d:%02d (day_fact + week_fact + month_fact, 2 meses).",
                        settings.OMNIVIEW_REAL_REFRESH_HOUR,
                        settings.OMNIVIEW_REAL_REFRESH_MINUTE,
                    )

                if settings.OMNIVIEW_REAL_WATCHDOG_ENABLED:
                    wd_min = max(5, int(settings.OMNIVIEW_REAL_WATCHDOG_INTERVAL_MINUTES))
                    _omniview_real_refresh_scheduler.add_job(
                        run_real_data_watchdog,
                        "interval",
                        minutes=wd_min,
                        id="omniview_real_data_watchdog",
                        replace_existing=True,
                        max_instances=1,
                        coalesce=True,
                        misfire_grace_time=120,
                    )
                    jobs_registered.append("omniview_real_data_watchdog")
                    logger.info(
                        "Omniview REAL watchdog programado: cada %s min.",
                        wd_min,
                    )

                _omniview_real_refresh_scheduler.start()
                attach_omniview_scheduler(_omniview_real_refresh_scheduler)
                set_scheduler_active(jobs_registered)
                logger.info("APScheduler Omniview (refresh/watchdog) iniciado.")
            except Exception as e:
                set_scheduler_error(str(e)[:200])
                logger.exception(
                    "No se pudo iniciar Omniview APScheduler (continuando sin él): %s",
                    e,
                )


@app.on_event("shutdown")
async def shutdown_omniview_real_refresh_scheduler():
    global _omniview_real_refresh_scheduler
    if _omniview_real_refresh_scheduler is not None:
        try:
            _omniview_real_refresh_scheduler.shutdown(wait=False)
        except Exception as e:
            logger.debug("shutdown scheduler: %s", e)
        _omniview_real_refresh_scheduler = None


@app.get("/")
async def root():
    return {
        "message": "YEGO Control Tower API - Fase 2A",
        "version": "2.0.0",
        "docs": "/docs"
    }
