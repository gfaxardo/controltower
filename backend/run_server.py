"""
Arranca la API con uvicorn usando host/puerto de settings.
Producción: BACKEND_HOST=127.0.0.1 BACKEND_PORT=8000 (solo nginx se conecta).
"""
import uvicorn
from app.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=(settings.ENVIRONMENT == "dev"),
    )
