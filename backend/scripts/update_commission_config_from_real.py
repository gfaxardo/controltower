"""
Actualiza ops.yego_commission_proxy_config con ratios reales calculados
de enero 2026 (el mes con mejor cobertura de comision_empresa_asociada).

Uso: cd backend && python -m scripts.update_commission_config_from_real
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db
from datetime import datetime

RULES = [
    # (country, city, park_id, tipo_servicio, pct, priority, notes)
    (None, None, None, None, 0.03, 0,
     "Default global 3% — confirmado por mediana real enero 2026 (mediana=3.00%, avg=2.96%)"),
    ("colombia", None, None, None, 0.03, 5,
     "Colombia genérico 3% — confirmado (avg=2.86%, mediana=3.00%)"),
    ("peru", None, None, None, 0.03, 5,
     "Perú genérico 3% — confirmado (avg=3.04%, mediana=3.00%)"),
    ("colombia", "bogota", None, None, 0.04, 10,
     "Bogotá 4% — ratio real avg=4.00%, mediana=4.00%, stddev=0.0005. Claramente diferente."),
    ("colombia", "cucuta", None, None, 0.025, 10,
     "Cúcuta 2.5% — ratio real avg=2.66%, mediana=2.50%, stddev=0.0024"),
    (None, None, None, "Moto", 0.025, 8,
     "Moto global 2.5% — ratio real avg=2.50%, mediana=2.50% (96K viajes)"),
    (None, None, None, "Cargo", 0.04, 8,
     "Cargo global 4% — ratio real avg=3.96%, mediana=4.00% (4.9K viajes)"),
    (None, None, None, "Mensajería", 0.035, 8,
     "Mensajería global 3.5% — ratio real avg=3.35%, mediana=3.64% (12.9K viajes)"),
]

with get_db() as conn:
    cur = conn.cursor()
    for country, city, park_id, tipo_servicio, pct, priority, notes in RULES:
        cur.execute("""
            INSERT INTO ops.yego_commission_proxy_config
                (country, city, park_id, tipo_servicio, commission_pct,
                 valid_from, valid_to, priority, is_active, notes)
            VALUES (%s, %s, %s, %s, %s, '2020-01-01', '2099-12-31', %s, TRUE, %s)
            ON CONFLICT DO NOTHING
        """, (country, city, park_id, tipo_servicio, pct, priority, notes))
    cur.close()

print(f"Config actualizada: {datetime.now()}")
print("Reglas insertadas:")
for c, ci, p, ts, pct, pr, n in RULES:
    ctx = "/".join(filter(None, [c, ci, ts])) or "GLOBAL"
    print(f"  {ctx}: {pct*100:.1f}% (priority={pr})")
