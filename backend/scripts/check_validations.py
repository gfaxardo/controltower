"""Script para verificar validaciones insertadas."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import init_db_pool, get_db

plan_version = sys.argv[1] if len(sys.argv) > 1 else 'ruta27_v2026_01_16_a'
init_db_pool()
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ops.plan_validation_results WHERE plan_version = %s", (plan_version,))
    count = cursor.fetchone()[0]
    print(f"Validaciones encontradas para {plan_version}: {count}")
    if count > 0:
        cursor.execute("SELECT validation_type, severity, COUNT(*) FROM ops.plan_validation_results WHERE plan_version = %s GROUP BY validation_type, severity ORDER BY validation_type, severity", (plan_version,))
        for row in cursor.fetchall():
            print(f"  - {row[0]} ({row[1]}): {row[2]}")
    cursor.close()
