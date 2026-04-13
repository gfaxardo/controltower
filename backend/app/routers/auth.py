"""
Login corporativo: el navegador llama solo a POST /auth/login en este mismo backend (vía nginx /api/);
aquí se reenvía a api-int con httpx — sin CORS en el cliente hacia api-int.
"""
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login_proxy(body: LoginBody):
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            settings.INTEGRAL_AUTH_LOGIN_URL,
            json=body.model_dump(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
    try:
        data = r.json()
    except Exception:
        data = {"detail": (r.text or "")[:500]}
    return JSONResponse(content=data, status_code=r.status_code)
