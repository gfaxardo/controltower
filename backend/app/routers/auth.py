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
    try:
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
    except httpx.ConnectError:
        return JSONResponse(
            content={"detail": "Servicio de autenticación no disponible. Reintenta en unos minutos."},
            status_code=503,
        )
    except httpx.TimeoutException:
        return JSONResponse(
            content={"detail": "El servicio de autenticación no respondió a tiempo. Reintenta."},
            status_code=504,
        )
    except Exception as e:
        return JSONResponse(
            content={"detail": f"Error interno de autenticación: {str(e)}"},
            status_code=502,
        )
