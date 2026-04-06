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
            SELECT
                COUNT(*)::bigint AS total_rows,
                COUNT(*) FILTER (WHERE condicion = 'Completado')::bigint AS completado,
                COUNT(*) FILTER (WHERE lower(coalesce(condicion::text, '')) LIKE '%cancel%')::bigint AS cancel_like,
                COUNT(*) FILTER (WHERE length(trim(coalesce(motivo_cancelacion::text, ''))) > 0)::bigint AS motivo_cancelacion_present,
                COUNT(*) FILTER (
                    WHERE condicion = 'Completado'
                      AND length(trim(coalesce(motivo_cancelacion::text, ''))) > 0
                )::bigint AS completado_con_motivo_cancelacion
            FROM public.trips_unified
            """
        )
        quality = dict(cur.fetchone())
        cur.execute(
            """
            SELECT
                CASE
                    WHEN fecha_inicio_viaje >= '2026-01-01'::date THEN 'trips_2026'
                    ELSE 'historical_pre_2026'
                END AS source_bucket,
                COUNT(*)::bigint AS rows
            FROM public.trips_unified
            GROUP BY 1
            ORDER BY 2 DESC
            """
        )
        buckets = [dict(r) for r in cur.fetchall()]
        cur.close()

    total = quality["total_rows"] or 0
    quality["completado_pct"] = round((quality["completado"] / total) * 100, 2) if total else None
    quality["cancel_like_pct"] = round((quality["cancel_like"] / total) * 100, 2) if total else None
    quality["motivo_cancelacion_present_pct"] = round((quality["motivo_cancelacion_present"] / total) * 100, 2) if total else None
    quality["completado_con_motivo_cancelacion_pct"] = round((quality["completado_con_motivo_cancelacion"] / total) * 100, 4) if total else None

    print(json.dumps({"quality": quality, "source_buckets": buckets}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
