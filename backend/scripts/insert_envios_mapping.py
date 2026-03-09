#!/usr/bin/env python3
"""Inserta mapping envíos -> delivery en la capa canónica (dim_real_service_type_lob)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import init_db_pool, get_db
init_db_pool()
with get_db() as conn:
    cur = conn.cursor()
    # Fuente canónica única (070+): solo dim
    cur.execute("""
        INSERT INTO canon.dim_real_service_type_lob (service_type_norm, lob_group, mapping_source, is_active, notes, updated_at)
        VALUES ('envíos', 'delivery', 'manual', true, 'Variante con tilde; envios ya mapeado', now())
        ON CONFLICT (service_type_norm) DO UPDATE SET lob_group = EXCLUDED.lob_group, updated_at = now()
    """)
    conn.commit()
    print("OK: envíos -> delivery (canon.dim_real_service_type_lob)")
