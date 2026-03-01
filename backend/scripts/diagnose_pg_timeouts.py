#!/usr/bin/env python3
"""
Diagnóstico de timeouts en sesión Postgres.
Identifica qué está forzando statement_timeout=15s y si SET puede aplicarse.

Uso:
  cd backend && python -m scripts.diagnose_pg_timeouts

Exit: 0 si SET aplicó correctamente, 2 si no se pudo o hay forcing detectado.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor


def _show_val(row):
    return list(row.values())[0] if row else "?"


def _parse_timeout_seconds(val: str) -> int | None:
    """Convierte '15s', '60min', '1h' a segundos aproximados. None si no parseable."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip().lower()
    try:
        if val.endswith("s"):
            return int(val[:-1])
        if val.endswith("min"):
            return int(val[:-3]) * 60
        if val.endswith("ms"):
            return int(val[:-2]) // 1000
        if val.endswith("h"):
            return int(val[:-1]) * 3600
        if val == "0":
            return 0
        return int(val)  # asumir segundos
    except (ValueError, TypeError):
        return None


def main() -> int:
    init_db_pool()

    with get_db() as conn:
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)

        print("=== DIAGNÓSTICO PG TIMEOUTS ===\n")

        # 1) Info de sesión
        cur.execute("SELECT current_user AS u, current_database() AS d")
        r = cur.fetchone()
        print("Sesión:")
        print("  current_user =", r.get("u", "?"))
        print("  current_database =", r.get("d", "?"))

        # 2) Valores actuales
        cur.execute("SHOW statement_timeout")
        st1 = _show_val(cur.fetchone())
        cur.execute("SHOW lock_timeout")
        lt1 = _show_val(cur.fetchone())
        cur.execute("SHOW idle_in_transaction_session_timeout")
        idle1 = _show_val(cur.fetchone())
        print("\nValores actuales:")
        print("  statement_timeout =", st1)
        print("  lock_timeout =", lt1)
        print("  idle_in_transaction_session_timeout =", idle1)

        # 3) TEST DEFINITIVO
        print("\n--- TEST DEFINITIVO ---")
        cur.execute("SHOW statement_timeout")
        antes = _show_val(cur.fetchone())
        cur.execute("SET statement_timeout = '60min'")
        cur.execute("SHOW statement_timeout")
        despues = _show_val(cur.fetchone())

        print("Antes:", antes)
        print("Después:", despues)

        # Validar: si sigue 15s o no contiene 60/min
        despues_lower = (despues or "").lower()
        antes_sec = _parse_timeout_seconds(str(antes or ""))
        despues_sec = _parse_timeout_seconds(str(despues or ""))

        ok = (
            ("60" in despues_lower or "min" in despues_lower or "1h" in despues_lower)
            and (despues_sec is None or despues_sec > 15)
            and "15s" not in despues_lower
        )

        if not ok:
            print("\nERROR: No se pudo aplicar SET statement_timeout en esta sesión.")
            print("Resultado esperado: 60min o 1h. Resultado obtenido:", despues)

            # 4) Diagnosticar configuraciones forzadas
            print("\n--- DIAGNÓSTICO DE FORZADO ---")

            # a) Roles
            cur.execute("""
                SELECT rolname, rolconfig FROM pg_roles WHERE rolconfig IS NOT NULL
            """)
            roles = cur.fetchall()
            for row in roles:
                cfg = row.get("rolconfig")
                if cfg and any("statement_timeout" in str(c).lower() for c in cfg):
                    print(f"  Rol {row['rolname']}: rolconfig = {cfg}")

            # b) DB configs
            cur.execute("""
                SELECT datname, datconfig FROM pg_database WHERE datconfig IS NOT NULL
            """)
            dbs = cur.fetchall()
            for row in dbs:
                cfg = row.get("datconfig")
                if cfg and any("statement_timeout" in str(c).lower() for c in cfg):
                    print(f"  DB {row['datname']}: datconfig = {cfg}")

            # c) pg_settings
            cur.execute("""
                SELECT name, setting, unit, source, sourcefile, sourceline
                FROM pg_settings
                WHERE name IN ('statement_timeout', 'lock_timeout')
            """)
            for row in cur.fetchall():
                print(f"  pg_settings: {row['name']} = {row['setting']} {row['unit'] or ''} (source={row['source']})")

            # 5) Recomendaciones
            print("\n--- RECOMENDACIONES ---")

            cur.execute("""
                SELECT rolname, rolconfig FROM pg_roles
                WHERE rolconfig IS NOT NULL
                AND EXISTS (
                    SELECT 1 FROM unnest(rolconfig) c
                    WHERE c::text ILIKE '%statement_timeout%'
                )
            """)
            for row in cur.fetchall():
                print(f"  Está forzado por ROL <{row['rolname']}>")
                print(f"    Solución sugerida: ALTER ROLE {row['rolname']} SET statement_timeout TO '60min';")

            cur.execute("""
                SELECT datname, datconfig FROM pg_database
                WHERE datconfig IS NOT NULL
                AND EXISTS (
                    SELECT 1 FROM unnest(datconfig) c
                    WHERE c::text ILIKE '%statement_timeout%'
                )
            """)
            for row in cur.fetchall():
                print(f"  Está forzado por DB <{row['datname']}>")
                print(f"    Solución sugerida: ALTER DATABASE {row['datname']} SET statement_timeout TO '60min';")

            cur.execute("""
                SELECT name, source FROM pg_settings
                WHERE name = 'statement_timeout' AND source = 'configuration file'
            """)
            if cur.fetchone():
                print("  Está en postgresql.conf o include file.")
                print("    Solución: editar postgresql.conf o ALTER ROLE/ALTER DATABASE para override.")

            cur.execute("""
                SELECT name, source FROM pg_settings
                WHERE name = 'statement_timeout' AND source = 'client'
            """)
            if cur.fetchone():
                print("  PGOPTIONS o driver lo impone.")

            cur.close()
            print("\n=== FIN DIAGNÓSTICO (exit 2) ===")
            return 2

        # OK
        print("\nResultado: OK. SET statement_timeout aplicó correctamente.")
        cur.close()
        print("\n=== FIN DIAGNÓSTICO (exit 0) ===")
        return 0


if __name__ == "__main__":
    sys.exit(main())
