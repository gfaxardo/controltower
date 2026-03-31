"""Cancela consultas activas largas (>60s) del usuario actual. Ejecutar una vez."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db


def main() -> None:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT pid, now() - query_start AS running_for,
                   left(query, 120) AS q
            FROM pg_stat_activity
            WHERE pid <> pg_backend_pid()
              AND state = 'active'
              AND now() - query_start > interval '60 seconds'
            ORDER BY query_start
            """
        )
        rows = cur.fetchall()
        if not rows:
            print("No hay consultas activas >60s. Todo limpio.")
            return
        for pid, dur, q in rows:
            print(f"  pid={pid} running={dur}  query={q}")
        print(f"\nCancelando {len(rows)} consulta(s)...")
        for pid, _, _ in rows:
            cur.execute("SELECT pg_cancel_backend(%s)", (pid,))
            print(f"  pg_cancel_backend({pid}) -> {cur.fetchone()[0]}")
        conn.commit()
        print("Hecho. Las sesiones deberían liberar temp files.")


if __name__ == "__main__":
    main()
