"""
Proxy de login Control Tower → API corporativa YEGO (api-int.yego.pro).
Evita CORS; mismo contrato que el login corporativo.
"""
import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class IntegralLoginBody(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/login")
async def integral_login(body: IntegralLoginBody) -> JSONResponse:
    """
    Reenvía POST {username, password} a INTEGRAL_AUTH_LOGIN_URL.
    Devuelve el mismo status y JSON que la API Integral (ej. 200 + token, o 401 + message).
    """
    url = (settings.INTEGRAL_AUTH_LOGIN_URL or "").strip()
    if not url:
        raise HTTPException(status_code=503, detail="Login no configurado (INTEGRAL_AUTH_LOGIN_URL)")

    payload: Dict[str, str] = {"username": body.username.strip(), "password": body.password}

    try:
        async with httpx.AsyncClient(timeout=25.0, verify=True) as client:
            r = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
    except httpx.RequestError as e:
        logger.warning("Integral login: error de red: %s", e)
        raise HTTPException(
            status_code=502,
            detail="No se pudo contactar el servicio de autenticación. Inténtalo más tarde.",
        )

    try:
        data: Any = r.json() if r.content else {}
    except Exception:
        data = {"message": r.text[:500] if r.text else "Respuesta no JSON"}

    return JSONResponse(status_code=r.status_code, content=data if isinstance(data, dict) else {"data": data})
