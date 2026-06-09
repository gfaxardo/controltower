from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.startup_state import get_startup_report
from app.db.connection import get_db
from app.services.scheduler_status_service import get_scheduler_status

router = APIRouter(tags=["health"])

_app_start_ts = None


def _get_app_start_time() -> str | None:
    global _app_start_ts
    if _app_start_ts:
        return _app_start_ts
    try:
        from app.services.omniview_v1_runtime_identity import get_v1_runtime_identity
        rid = get_v1_runtime_identity()
        _app_start_ts = rid.get("app_start_time")
        return _app_start_ts
    except Exception:
        return None


def _get_runtime_identity() -> dict | None:
    try:
        from app.services.omniview_v1_runtime_identity import get_v1_runtime_identity
        return get_v1_runtime_identity()
    except Exception:
        return None


@router.get("/health")
async def health_check():
    """
    Estado global: ok | degraded | blocked.
    - blocked: pool DB caído o startup bloqueado (503).
    - degraded: arranque completó con advertencias (200 + cuerpo explícito).
    - ok: operativo.
    """
    db_ok = True
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
    except Exception:
        db_ok = False

    rep = get_startup_report()
    overall = rep.get("overall", "unknown")
    if not db_ok:
        overall = "blocked"

    startup_slim = {
        "overall": rep.get("overall"),
        "environment": rep.get("environment"),
        "checks": rep.get("checks"),
        "inspection_ok": bool(rep.get("inspection")) and not (rep.get("inspection") or {}).get("_error"),
    }

    scheduler = get_scheduler_status()

    body = {
        "status": overall,
        "service": "YEGO Control Tower API",
        "db_connection": "ok" if db_ok else "down",
        "startup": startup_slim,
        "scheduler_status": scheduler["status"],
        "scheduler_detail": scheduler["detail"],
        "scheduler_jobs": scheduler["jobs"],
    }

    # OMNI-V1 HARDENING: Runtime Identity (additive, non-breaking)
    rid = _get_runtime_identity()
    if rid:
        body["runtime_identity"] = {
            "git_hash": rid.get("git_hash"),
            "git_branch": rid.get("git_branch"),
            "build_time": rid.get("build_time"),
            "backend_instance": rid.get("backend_instance"),
            "python_version": rid.get("python_version"),
            "app_start_time": rid.get("app_start_time"),
            "pycache_risk_checked": rid.get("pycache_risk_checked"),
        }

    code = 503 if overall == "blocked" else 200
    return JSONResponse(status_code=code, content=body)




