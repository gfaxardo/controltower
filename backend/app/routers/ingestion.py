from fastapi import APIRouter, HTTPException
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

@router.get("/status")
async def get_ingestion_status(dataset_name: str = "real_monthly_agg") -> Dict:
    """
    Obtiene el estado de ingesta para un dataset.
    Retorna max_year, max_month, is_complete_2025, last_loaded_at.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT dataset_name, max_year, max_month, last_loaded_at, is_complete_2025
                FROM bi.ingestion_status
                WHERE dataset_name = %s
            """, (dataset_name,))
            result = cursor.fetchone()
            cursor.close()
            
            if not result:
                return {
                    "dataset_name": dataset_name,
                    "max_year": None,
                    "max_month": None,
                    "last_loaded_at": None,
                    "is_complete_2025": False
                }
            
            return dict(result)
            
    except Exception as e:
        logger.error(f"Error al obtener estado de ingesta: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estado de ingesta: {str(e)}")




