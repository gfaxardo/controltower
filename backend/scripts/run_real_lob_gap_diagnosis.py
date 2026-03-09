#!/usr/bin/env python3
"""
Diagnóstico end-to-end: brecha service_type -> LOB (Real LOB).
- Introspección del schema (objetos reales en ops, canon, dim, public).
- Ejecución de consultas de diagnóstico sobre objetos encontrados.
- Clasificación del residual (LEGIT_NO_MAPPING, GARBAGE, etc.).
- Corrección mínima: insertar en canon.map_real_tipo_servicio_to_lob_group si hay legítimos.
- Evidencia escrita en docs y en JSON para el resumen ejecutivo.

Uso (desde backend): python scripts/run_real_lob_gap_diagnosis.py
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

# Salida para evidencia y docs
EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docs")
os.makedirs(EVIDENCE_DIR, exist_ok=True)
OUTPUT_JSON = os.path.join(EVIDENCE_DIR, "real_lob_gap_evidence.json")


def run_sql(cur, sql, params=None, comment=""):
    cur.execute(sql, params or ())
    return cur.fetchall()


def main():
    init_db_pool()
    evidence = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "schema_introspection": {},
        "diagnosis": {},
        "residual_classification": [],
        "mappings_added": [],
        "validation_after": {},
        "errors": [],
    }

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Limitar tiempo por consulta (vista base puede ser pesada)
        try:
            cur.execute("SET statement_timeout = '20000'")  # 20 s por statement (vista base pesada)
        except Exception:
            pass
        try:
            # ----- FASE A: Introspección del schema -----
            # Tablas
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema IN ('ops','canon','dim','public')
                  AND ( table_name ILIKE %s OR table_name ILIKE %s OR table_name ILIKE %s
                        OR table_name ILIKE %s OR table_name ILIKE %s OR table_name ILIKE %s )
                ORDER BY 1, 2
            """, ('%real_lob%', '%trips%lob%', '%drill%', '%service_type%', '%tipo_servicio%', '%lob%'))
            tables = [dict(r) for r in cur.fetchall()]
            evidence["schema_introspection"]["tables"] = tables

            # Vistas
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.views
                WHERE table_schema IN ('ops','canon','dim','public')
                  AND ( table_name ILIKE %s OR table_name ILIKE %s OR table_name ILIKE %s
                        OR table_name ILIKE %s OR table_name ILIKE %s OR table_name ILIKE %s )
                ORDER BY 1, 2
            """, ('%real_lob%', '%trips%lob%', '%drill%', '%service_type%', '%tipo_servicio%', '%lob%'))
            views = [dict(r) for r in cur.fetchall()]
            evidence["schema_introspection"]["views"] = views

            # Funciones (ops, canon)
            cur.execute("""
                SELECT n.nspname AS schema_name, p.proname AS function_name
                FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname IN ('ops','canon')
                  AND ( p.proname ILIKE %s OR p.proname ILIKE %s OR p.proname ILIKE %s
                        OR p.proname ILIKE %s OR p.proname ILIKE %s )
                ORDER BY 1, 2
            """, ('%service_type%', '%tipo_servicio%', '%lob%', '%normalize%', '%validate%'))
            funcs = [dict(r) for r in cur.fetchall()]
            evidence["schema_introspection"]["functions"] = funcs

            # Confirmar objeto base: vista con real_tipo_servicio_norm + lob_group
            base_candidates = []
            for v in views:
                sch, name = v["table_schema"], v["table_name"]
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                """, (sch, name))
                cols = [r["column_name"] for r in cur.fetchall()]
                if "lob_group" in cols and ("real_tipo_servicio_norm" in cols or "tipo_servicio_norm" in cols):
                    base_candidates.append({"schema": sch, "table_name": name, "columns": cols})
            evidence["schema_introspection"]["base_candidates_with_lob_and_service_type"] = base_candidates

            # Objeto base elegido: preferir v_real_trips_with_lob_v2 (tiene real_tipo_servicio_norm)
            base_schema, base_table, base_st_col = None, None, None
            for c in base_candidates:
                if c["table_name"] == "v_real_trips_with_lob_v2" and c["schema"] == "ops":
                    base_schema, base_table = c["schema"], c["table_name"]
                    base_st_col = "real_tipo_servicio_norm"
                    break
            if not base_schema and base_candidates:
                c = base_candidates[0]
                base_schema, base_table = c["schema"], c["table_name"]
                base_st_col = "real_tipo_servicio_norm" if "real_tipo_servicio_norm" in c["columns"] else "tipo_servicio_norm"
            evidence["schema_introspection"]["chosen_base"] = {"schema": base_schema, "table_name": base_table, "service_type_column": base_st_col}

            # Tabla de diagnóstico (para B/C sin escanear vista pesada)
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ops.real_lob_residual_diagnostic (
                        validated_service_type text, lob_group text, trips bigint NOT NULL DEFAULT 0,
                        PRIMARY KEY (validated_service_type, lob_group)
                    )
                """)
                conn.commit()
            except Exception:
                conn.rollback()

            # Fact drill: real_drill_dim_fact
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'ops' AND table_name = 'real_drill_dim_fact'
                ORDER BY ordinal_position
            """)
            drill_cols = [r["column_name"] for r in cur.fetchall()] if cur.rowcount else []
            evidence["schema_introspection"]["real_drill_dim_fact_columns"] = drill_cols
            has_drill = "ops.real_drill_dim_fact" in [f"{t['table_schema']}.{t['table_name']}" for t in tables]

            # ----- FASE B: Diagnóstico SQL -----
            # A) Residual UNCLASSIFIED en drill (service_type y lob)
            if has_drill:
                cur.execute("""
                    SELECT breakdown, dimension_key AS breakdown_value, SUM(trips)::bigint AS trips
                    FROM ops.real_drill_dim_fact
                    WHERE breakdown IN ('service_type','lob') AND dimension_key = 'UNCLASSIFIED'
                    GROUP BY breakdown, dimension_key
                    ORDER BY breakdown
                """)
                evidence["diagnosis"]["A_residual_drill"] = [dict(r) for r in cur.fetchall()]
            else:
                evidence["diagnosis"]["A_residual_drill"] = []
                evidence["errors"].append("ops.real_drill_dim_fact not found")

            # Preferir tabla de diagnóstico si tiene datos (evita escanear vista pesada)
            use_diagnostic_table = False
            try:
                cur.execute("SELECT COUNT(*) FROM ops.real_lob_residual_diagnostic")
                use_diagnostic_table = (cur.fetchone().get("count", 0) or 0) > 0
            except Exception:
                conn.rollback()

            date_filter = " AND fecha_inicio_viaje::date >= (current_date - 90) " if base_schema and base_table else ""
            # B) Top validated_service_type en LOB UNCLASSIFIED
            if use_diagnostic_table:
                try:
                    cur.execute("""
                        SELECT validated_service_type, trips FROM ops.real_lob_residual_diagnostic
                        WHERE lob_group = 'UNCLASSIFIED'
                        ORDER BY trips DESC LIMIT 200
                    """)
                    evidence["diagnosis"]["B_top_unclassified_lob"] = [dict(r) for r in cur.fetchall()]
                    evidence["diagnosis"]["B_source"] = "ops.real_lob_residual_diagnostic"
                except Exception as e:
                    conn.rollback()
                    evidence["diagnosis"]["B_top_unclassified_lob"] = []
                    evidence["errors"].append(f"B from diagnostic table: {e}")
            elif base_schema and base_table:
                try:
                    q = f"""
                        SELECT {base_st_col} AS validated_service_type, COUNT(*)::bigint AS trips
                        FROM {base_schema}.{base_table}
                        WHERE lob_group = 'UNCLASSIFIED' {date_filter}
                        GROUP BY {base_st_col}
                        ORDER BY trips DESC
                        LIMIT 200
                    """
                    cur.execute(q)
                    evidence["diagnosis"]["B_top_unclassified_lob"] = [dict(r) for r in cur.fetchall()]
                    evidence["diagnosis"]["B_source"] = f"{base_schema}.{base_table}"
                except Exception as e:
                    conn.rollback()
                    evidence["diagnosis"]["B_top_unclassified_lob"] = []
                    evidence["errors"].append(f"B query failed (view slow?): {e}")
            else:
                evidence["diagnosis"]["B_top_unclassified_lob"] = []
                evidence["errors"].append("No base object with lob_group + service type column found")

            # C) Cruzado validated_service_type x lob_group
            if use_diagnostic_table:
                try:
                    cur.execute("""
                        SELECT validated_service_type, lob_group, trips
                        FROM ops.real_lob_residual_diagnostic
                        ORDER BY trips DESC LIMIT 500
                    """)
                    evidence["diagnosis"]["C_cross_service_lob"] = [dict(r) for r in cur.fetchall()]
                except Exception as e:
                    conn.rollback()
                    evidence["diagnosis"]["C_cross_service_lob"] = []
                    evidence["errors"].append(f"C from diagnostic table: {e}")
            elif base_schema and base_table:
                try:
                    q = f"""
                        SELECT {base_st_col} AS validated_service_type, lob_group, COUNT(*)::bigint AS trips
                        FROM {base_schema}.{base_table}
                        WHERE 1=1 {date_filter}
                        GROUP BY {base_st_col}, lob_group
                        ORDER BY trips DESC
                        LIMIT 500
                    """
                    cur.execute(q)
                    evidence["diagnosis"]["C_cross_service_lob"] = [dict(r) for r in cur.fetchall()]
                except Exception as e:
                    conn.rollback()
                    evidence["diagnosis"]["C_cross_service_lob"] = []
                    evidence["errors"].append(f"C query failed: {e}")
            else:
                evidence["diagnosis"]["C_cross_service_lob"] = []

            # D) Totales y % UNCLASSIFIED
            if use_diagnostic_table:
                try:
                    cur.execute("""
                        SELECT SUM(trips)::bigint AS total_trips,
                               SUM(CASE WHEN lob_group = 'UNCLASSIFIED' THEN trips ELSE 0 END)::bigint AS unclassified_lob_trips,
                               ROUND(100.0 * SUM(CASE WHEN lob_group = 'UNCLASSIFIED' THEN trips ELSE 0 END) / NULLIF(SUM(trips), 0), 4) AS pct_unclassified_lob
                        FROM ops.real_lob_residual_diagnostic
                    """)
                    row = cur.fetchone()
                    evidence["diagnosis"]["D_totals"] = dict(row) if row else {}
                except Exception as e:
                    conn.rollback()
                    evidence["diagnosis"]["D_totals"] = {}
                    evidence["errors"].append(f"D from diagnostic table: {e}")
            elif base_schema and base_table:
                try:
                    cur.execute(f"""
                        SELECT COUNT(*)::bigint AS total_trips,
                               SUM(CASE WHEN lob_group = 'UNCLASSIFIED' THEN 1 ELSE 0 END)::bigint AS unclassified_lob_trips,
                               ROUND(100.0 * SUM(CASE WHEN lob_group = 'UNCLASSIFIED' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) AS pct_unclassified_lob
                        FROM {base_schema}.{base_table}
                        WHERE 1=1 {date_filter}
                    """)
                    row = cur.fetchone()
                    evidence["diagnosis"]["D_totals"] = dict(row) if row else {}
                except Exception as e:
                    conn.rollback()
                    evidence["diagnosis"]["D_totals"] = {}
                    evidence["errors"].append(f"D query failed: {e}")
            else:
                evidence["diagnosis"]["D_totals"] = {}

            # ----- Clasificación del residual -----
            # LEGIT_NO_MAPPING: valores que parecen tipo de servicio de negocio (ej. variantes conocidas)
            KNOWN_LEGIT_PATTERNS = {
                "confort_plus", "confort plus", "comfort", "comfort+", "xl", "premiere",
                "mensajeria", "exprés", "exprs", "economico", "económico",
                "minivan", "express", "premier", "moto", "cargo", "standard", "start",
                "tuk-tuk", "tuk tuk", "delivery", "taxi"
            }
            GARBAGE_PATTERNS = ("->", "null", "none", "test", "id:", "nan", "undefined")
            def is_likely_garbage(v):
                if not v or str(v).strip() == "":
                    return True
                vl = str(v).strip().lower()
                if len(vl) > 40 or vl.isdigit() or any(g in vl for g in GARBAGE_PATTERNS):
                    return True
                return False

            classification = []
            for row in evidence["diagnosis"].get("B_top_unclassified_lob", []):
                v = row.get("validated_service_type")
                trips = row.get("trips") or 0
                if v is None or (isinstance(v, str) and str(v).strip() == ""):
                    classification.append({"validated_service_type": v, "trips": trips, "category": "NULL_OR_EMPTY"})
                    continue
                if str(v).strip().lower() == "unclassified":
                    classification.append({"validated_service_type": v, "trips": trips, "category": "ALREADY_UNCLASSIFIED"})
                    continue
                if is_likely_garbage(v):
                    classification.append({"validated_service_type": v, "trips": trips, "category": "GARBAGE"})
                    continue
                # Posible legítimo: normalizar y ver si ya está en mapping
                vn = str(v).strip().lower().replace(" ", "-").replace("_", "-")
                vn_ascii = (vn.replace("í", "i").replace("é", "e").replace("ó", "o").replace("á", "a").replace("ú", "u").replace("ñ", "n"))
                if any(p in vn_ascii or vn_ascii in p or p in vn or vn in p for p in ["confort", "comfort", "express", "mensajer", "econom", "premier", "minivan", "moto", "cargo", "tuk", "standard", "start", "xl", "envio"]):
                    classification.append({"validated_service_type": v, "trips": trips, "category": "LEGIT_NO_MAPPING"})
                else:
                    classification.append({"validated_service_type": v, "trips": trips, "category": "UNKNOWN_NEEDS_REVIEW"})
            evidence["residual_classification"] = classification

            # ----- FASE C: Corrección mínima -----
            # Obtener mapping actual
            cur.execute("SELECT real_tipo_servicio, lob_group FROM canon.map_real_tipo_servicio_to_lob_group ORDER BY 1")
            current_mapping = {r["real_tipo_servicio"]: r["lob_group"] for r in cur.fetchall()}
            evidence["current_mapping_keys"] = list(current_mapping.keys())

            # LOBs permitidos (taxonomía actual)
            LOB_GROUPS = {"auto taxi", "delivery", "tuk tuk", "taxi moto"}
            legit_to_add = []
            for item in classification:
                if item["category"] != "LEGIT_NO_MAPPING":
                    continue
                v = item["validated_service_type"]
                vn = str(v).strip().lower()
                vn_norm = vn.replace(" ", "-").replace("_", "-").replace("í", "i").replace("é", "e").replace("ó", "o").replace("á", "a").replace("ú", "u").replace("ñ", "n")
                key_in_map = str(v).strip() if v else vn_norm
                if key_in_map in current_mapping or vn_norm in current_mapping:
                    continue
                # Asignar LOB según patrón
                if "confort" in vn_norm or "comfort" in vn_norm or "xl" in vn_norm or "premier" in vn_norm or "minivan" in vn_norm or "standard" in vn_norm or "start" in vn_norm or "econom" in vn_norm:
                    lob = "auto taxi"
                elif "express" in vn_norm or "mensajer" in vn_norm or "cargo" in vn_norm or "delivery" in vn_norm or "envio" in vn_norm:
                    lob = "delivery"
                elif "tuk" in vn_norm:
                    lob = "tuk tuk"
                elif "moto" in vn_norm:
                    lob = "taxi moto"
                else:
                    lob = "auto taxi"  # default conservador
                legit_to_add.append({"real_tipo_servicio": key_in_map, "lob_group": lob, "trips": item["trips"]})

            for add in legit_to_add:
                try:
                    cur.execute("""
                        INSERT INTO canon.map_real_tipo_servicio_to_lob_group (real_tipo_servicio, lob_group)
                        VALUES (%s, %s)
                        ON CONFLICT (real_tipo_servicio) DO UPDATE SET lob_group = EXCLUDED.lob_group
                    """, (add["real_tipo_servicio"], add["lob_group"]))
                    # Capa canónica (070+): mantener dim como fuente de verdad
                    cur.execute("""
                        INSERT INTO canon.dim_real_service_type_lob (service_type_norm, lob_group, mapping_source, is_active, notes, updated_at)
                        VALUES (%s, %s, 'manual', true, 'Añadido por run_real_lob_gap_diagnosis', now())
                        ON CONFLICT (service_type_norm) DO UPDATE SET lob_group = EXCLUDED.lob_group, updated_at = now()
                    """, (add["real_tipo_servicio"], add["lob_group"]))
                    evidence["mappings_added"].append(add)
                except Exception as e:
                    evidence["errors"].append(f"Insert mapping {add}: {e}")

            conn.commit()  # Commit mappings antes de validación (por si la validación hace timeout)

            # ----- FASE F: Validación posterior (misma conexión) -----
            if base_schema and base_table:
                cur.execute(f"""
                    SELECT {base_st_col} AS validated_service_type, COUNT(*)::bigint AS trips
                    FROM {base_schema}.{base_table}
                    WHERE lob_group = 'UNCLASSIFIED' {date_filter}
                    GROUP BY {base_st_col}
                    ORDER BY trips DESC
                    LIMIT 100
                """)
                evidence["validation_after"]["top_still_unclassified"] = [dict(r) for r in cur.fetchall()]
            if has_drill:
                cur.execute("""
                    SELECT breakdown, dimension_key AS breakdown_value, SUM(trips)::bigint AS trips
                    FROM ops.real_drill_dim_fact
                    WHERE breakdown IN ('service_type','lob') AND dimension_key = 'UNCLASSIFIED'
                    GROUP BY breakdown, dimension_key
                    ORDER BY breakdown
                """)
                evidence["validation_after"]["drill_unclassified_after"] = [dict(r) for r in cur.fetchall()]

        except Exception as e:
            evidence["errors"].append(str(e))
            conn.rollback()
        finally:
            cur.close()

    # Escribir evidencia JSON (siempre, incluso si hubo excepción)
    def json_serial(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if hasattr(obj, "__float__"):  # Decimal, etc.
            return float(obj)
        raise TypeError(type(obj).__name__)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False, default=json_serial)

    print("Evidence written to", OUTPUT_JSON)
    print("Schema: tables", len(evidence["schema_introspection"].get("tables", [])),
          "views", len(evidence["schema_introspection"].get("views", [])))
    print("Chosen base:", evidence["schema_introspection"].get("chosen_base"))
    print("A residual drill:", evidence["diagnosis"].get("A_residual_drill"))
    print("B top unclassified LOB:", (evidence["diagnosis"].get("B_top_unclassified_lob") or [])[:15])
    print("D totals:", evidence["diagnosis"].get("D_totals"))
    print("Mappings added:", evidence["mappings_added"])
    print("Errors:", evidence["errors"])
    return evidence


if __name__ == "__main__":
    main()
