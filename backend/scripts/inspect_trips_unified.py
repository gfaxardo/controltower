from __future__ import annotations

import json
import sys

from psycopg2.extras import RealDictCursor

sys.path.append(".")

from app.db.connection import get_db  # noqa: E402


def main() -> None:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT column_name, ordinal_position, data_type, character_maximum_length, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'trips_unified'
            ORDER BY ordinal_position
            """
        )
        columns = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT pg_get_viewdef('public.trips_unified'::regclass, true) AS view_sql")
        view_sql = cur.fetchone()["view_sql"]
        cur.close()
    print(json.dumps({"columns": columns, "view_sql": view_sql}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
