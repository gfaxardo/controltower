#!/usr/bin/env python3
"""
Rellena ops.real_lob_residual_diagnostic desde ops.v_real_trips_with_lob_v2 (últimos 90 días).
Consulta pesada; ejecutar una vez o tras backfill. Timeout sugerido: 10 min.

  cd backend && python scripts/populate_real_lob_residual_diagnostic.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '600000'")  # 10 min
        cur.execute("TRUNCATE ops.real_lob_residual_diagnostic")
        cur.execute("""
            INSERT INTO ops.real_lob_residual_diagnostic (validated_service_type, lob_group, trips)
            SELECT real_tipo_servicio_norm, lob_group, COUNT(*)::bigint
            FROM ops.v_real_trips_with_lob_v2
            WHERE fecha_inicio_viaje::date >= (current_date - 90)
            GROUP BY real_tipo_servicio_norm, lob_group
        """)
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM ops.real_lob_residual_diagnostic")
        n = cur.fetchone()[0]
        print("Rows in ops.real_lob_residual_diagnostic:", n)
        cur.close()

if __name__ == "__main__":
    main()
