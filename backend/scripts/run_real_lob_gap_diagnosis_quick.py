#!/usr/bin/env python3
"""Solo introspección + consulta A (drill fact). Escribe evidencia y sale. Sin consultas a vista pesada."""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docs")
os.makedirs(EVIDENCE_DIR, exist_ok=True)
OUTPUT_JSON = os.path.join(EVIDENCE_DIR, "real_lob_gap_evidence.json")

def main():
    init_db_pool()
    evidence = {"run_at": datetime.utcnow().isoformat() + "Z", "schema_introspection": {}, "diagnosis": {}, "errors": []}
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SET statement_timeout = '10000'")
        except Exception:
            pass
        try:
            cur.execute("""
                SELECT table_schema, table_name FROM information_schema.tables
                WHERE table_schema IN ('ops','canon','dim','public')
                  AND ( table_name ILIKE %s OR table_name ILIKE %s OR table_name ILIKE %s
                        OR table_name ILIKE %s OR table_name ILIKE %s OR table_name ILIKE %s )
                ORDER BY 1, 2
            """, ('%real_lob%', '%trips%lob%', '%drill%', '%service_type%', '%tipo_servicio%', '%lob%'))
            evidence["schema_introspection"]["tables"] = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT table_schema, table_name FROM information_schema.views
                WHERE table_schema IN ('ops','canon','dim','public')
                  AND ( table_name ILIKE %s OR table_name ILIKE %s OR table_name ILIKE %s
                        OR table_name ILIKE %s OR table_name ILIKE %s OR table_name ILIKE %s )
                ORDER BY 1, 2
            """, ('%real_lob%', '%trips%lob%', '%drill%', '%service_type%', '%tipo_servicio%', '%lob%'))
            evidence["schema_introspection"]["views"] = [dict(r) for r in cur.fetchall()]

            base_candidates = []
            for v in evidence["schema_introspection"]["views"]:
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                            (v["table_schema"], v["table_name"]))
                cols = [r["column_name"] for r in cur.fetchall()]
                if "lob_group" in cols and ("real_tipo_servicio_norm" in cols or "tipo_servicio_norm" in cols):
                    base_candidates.append({"schema": v["table_schema"], "table_name": v["table_name"], "columns": cols})
            evidence["schema_introspection"]["base_candidates_with_lob_and_service_type"] = base_candidates

            chosen = None
            for c in base_candidates:
                if c["table_name"] == "v_real_trips_with_lob_v2" and c["schema"] == "ops":
                    chosen = {"schema": c["schema"], "table_name": c["table_name"], "service_type_column": "real_tipo_servicio_norm"}
                    break
            if not chosen and base_candidates:
                c = base_candidates[0]
                chosen = {"schema": c["schema"], "table_name": c["table_name"],
                         "service_type_column": "real_tipo_servicio_norm" if "real_tipo_servicio_norm" in c["columns"] else "tipo_servicio_norm"}
            evidence["schema_introspection"]["chosen_base"] = chosen

            cur.execute("""
                SELECT breakdown, dimension_key AS breakdown_value, SUM(trips)::bigint AS trips
                FROM ops.real_drill_dim_fact
                WHERE breakdown IN ('service_type','lob') AND dimension_key = 'UNCLASSIFIED'
                GROUP BY breakdown, dimension_key ORDER BY breakdown
            """)
            evidence["diagnosis"]["A_residual_drill"] = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT real_tipo_servicio, lob_group FROM canon.map_real_tipo_servicio_to_lob_group ORDER BY 1")
            evidence["current_mapping"] = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            evidence["errors"].append(str(e))
            conn.rollback()
        finally:
            cur.close()

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)
    print("OK", OUTPUT_JSON)
    print("A_residual_drill", evidence.get("diagnosis", {}).get("A_residual_drill"))
    return evidence

if __name__ == "__main__":
    main()
