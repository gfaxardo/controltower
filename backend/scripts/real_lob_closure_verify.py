#!/usr/bin/env python3
"""
Verificación final CT-REAL-LOB-FINAL-CLOSURE.
Ejecutar tras completar bootstrap month y week.
Comprueba: conteos MVs, governance --skip-refresh, canonicalización.
Salida: resumen para rellenar Fase G.
"""
import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
except ImportError:
    pass


def main():
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    out = []

    with get_db() as conn:
        cur = conn.cursor()

        # Alembic
        cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
        r = cur.fetchone()
        alembic_current = r[0] if r else None
        out.append("E. Estado final Alembic: %s" % alembic_current)

        # Conteos
        try:
            cur.execute("SELECT COUNT(*) FROM ops.mv_real_lob_month_v2")
            month_count = cur.fetchone()[0]
        except Exception as e:
            conn.rollback()
            month_count = "ERROR: %s" % (str(e)[:80])
        try:
            cur.execute("SELECT COUNT(*) FROM ops.mv_real_lob_week_v2")
            week_count = cur.fetchone()[0]
        except Exception as e:
            conn.rollback()
            week_count = "ERROR: %s" % (str(e)[:80])

        out.append("F. Conteo final month_v2: %s" % month_count)
        out.append("G. Conteo final week_v2: %s" % week_count)

        # Canonicalización: variantes no deseadas (solo si month tiene datos)
        try:
            if isinstance(month_count, int) and month_count > 0:
                cur.execute("""
                    SELECT real_tipo_servicio_norm, COUNT(*) AS c
                    FROM ops.mv_real_lob_month_v2
                    WHERE real_tipo_servicio_norm IS NOT NULL
                    GROUP BY real_tipo_servicio_norm
                    ORDER BY c DESC
                """)
                rows = cur.fetchall()
                keys = [r[0] for r in rows] if rows else []
                bad = {"confort+", "confort plus", "comfort+", "tuk-tuk", "mensajería", "mensajeria", "express"}
                found_bad = [k for k in keys if k and k.lower() in bad]
                out.append("Canonicalización month_v2: variantes no canónicas = %s" % (found_bad or "ninguna"))
            else:
                out.append("Canonicalización: omitido (month_v2 sin datos)")
        except Exception as e:
            conn.rollback()
            out.append("Canonicalización: ERROR %s" % str(e)[:80])

    # Governance
    out.append("\nH. Resultado governance --skip-refresh:")
    gov_exit = -1
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "close_real_lob_governance.py"), "--skip-refresh"],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=400,
        )
        gov_exit = result.returncode
        out.append(result.stdout or "")
        if result.stderr:
            out.append("stderr: " + result.stderr[:500])
        out.append("exitcode: %s" % result.returncode)
    except Exception as e:
        out.append("ERROR ejecutando governance: %s" % e)

    print("\n".join(out))
    month_ok = isinstance(month_count, int) and month_count > 0
    week_ok = isinstance(week_count, int) and week_count > 0
    closed = alembic_current == "098_real_lob_root_cause_120d" and month_ok and week_ok and gov_exit == 0
    print("\nI. ¿Quedó cerrado? %s" % ("SÍ" if closed else "NO"))
    if not closed:
        if not month_ok:
            print("J. Bloqueo: month_v2 no poblada o error")
        elif not week_ok:
            print("J. Bloqueo: week_v2 no poblada o error")
        elif result.returncode != 0:
            print("J. Bloqueo: governance no PASS")
        else:
            print("J. Bloqueo: alembic no alineado a 098")
    return 0 if closed else 1


if __name__ == "__main__":
    sys.exit(main())
