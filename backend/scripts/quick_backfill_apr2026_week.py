"""Quick backfill for April 2026 week_fact"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db_audit
exec(open(os.path.join(os.path.dirname(__file__), "quick_backfill_may2026_week.py")).read().replace("2026-05-01", "2026-04-01").replace("2026-05-31", "2026-04-30"))
