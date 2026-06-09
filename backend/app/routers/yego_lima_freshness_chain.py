"""YEGO Lima Growth — Freshness Chain Router (LG-INFRA-R3.0C)"""
import logging
from fastapi import APIRouter
from app.services.yego_lima_freshness_chain_service import get_freshness_chain_status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/freshness-chain", tags=["yego-lima-growth-freshness-chain"])

@router.get("/status")
async def freshness_chain():
    return get_freshness_chain_status()
