from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.startup_state import get_startup_report
from app.db.connection import get_db

router = APIRouter(tags=["health"])


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

    body = {
        "status": overall,
        "service": "YEGO Control Tower API",
        "db_connection": "ok" if db_ok else "down",
        "startup": startup_slim,
    }
    code = 503 if overall == "blocked" else 200
    return JSONResponse(status_code=code, content=body)




