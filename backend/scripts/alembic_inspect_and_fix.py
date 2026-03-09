"""
Inspecciona y repara el estado de Alembic cuando la BD tiene una revisión que ya no existe en el repo.

Uso:
  python -m scripts.alembic_inspect_and_fix              # solo inspección (imprime alembic_version y heads)
  python -m scripts.alembic_inspect_and_fix --fix         # alinea a 069 y ejecuta upgrade head
  python -m scripts.alembic_inspect_and_fix --stamp 069  # solo UPDATE alembic_version a 069 (sin upgrade)

Cuando la BD tiene version_num = '073_normalize_expres_to_express' (u otra revisión fantasma) y ese
archivo ya no está en backend/alembic/versions/, Alembic falla con "Can't locate revision".
Estrategia recomendada: stamp a 069_real_lob_residual_diagnostic (última revisión antes de 070)
y luego ejecutar alembic upgrade head para aplicar 070 y sucesivas.
"""
import argparse
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def get_conn():
    from app.db.connection import _get_connection_params
    import psycopg2
    params = dict(_get_connection_params())
    params["options"] = "-c application_name=ct_alembic_inspect"
    return psycopg2.connect(**params)


def inspect(conn) -> dict:
    """Lee alembic_version y opcionalmente lista objetos de la capa canónica."""
    out = {"alembic_version": None, "rows": []}
    cur = conn.cursor()
    cur.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
    out["rows"] = [r[0] for r in cur.fetchall()]
    out["alembic_version"] = out["rows"][0] if out["rows"] else None
    cur.close()
    return out


def stamp(conn, revision: str) -> None:
    """Actualiza alembic_version a la revisión indicada (una sola fila)."""
    cur = conn.cursor()
    cur.execute("UPDATE alembic_version SET version_num = %s", (revision,))
    if cur.rowcount == 0:
        cur.execute("INSERT INTO alembic_version (version_num) VALUES (%s)", (revision,))
    conn.commit()
    cur.close()


def main():
    parser = argparse.ArgumentParser(description="Inspección y reparación de Alembic")
    parser.add_argument("--fix", action="store_true", help="Alinear a 069 y ejecutar alembic upgrade head")
    parser.add_argument("--stamp", metavar="REV", help="Solo actualizar alembic_version a REV (ej: 069_real_lob_residual_diagnostic)")
    args = parser.parse_args()

    print("=== Estado actual (antes) ===")
    try:
        conn = get_conn()
        conn.autocommit = False
        state = inspect(conn)
        print("alembic_version:", state["alembic_version"])
        if len(state["rows"]) > 1:
            print("Todas las filas:", state["rows"])
        conn.close()
    except Exception as e:
        print("Error conectando o leyendo:", e)
        return 1

    if args.stamp:
        conn = get_conn()
        conn.autocommit = False
        try:
            stamp(conn, args.stamp)
            print("Stamped alembic_version to:", args.stamp)
        finally:
            conn.close()
        return 0

    if args.fix:
        # Alinear a 069 para que upgrade head aplique 070
        TARGET_STAMP = "069_real_lob_residual_diagnostic"
        conn = get_conn()
        conn.autocommit = False
        try:
            stamp(conn, TARGET_STAMP)
        finally:
            conn.close()
        print("Stamped alembic_version to", TARGET_STAMP)
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env={**os.environ},
        )
        if result.returncode != 0:
            print("alembic upgrade head falló con código", result.returncode)
            return result.returncode
        print("=== Estado después de upgrade ===")
        conn = get_conn()
        state = inspect(conn)
        print("alembic_version:", state["alembic_version"])
        conn.close()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
