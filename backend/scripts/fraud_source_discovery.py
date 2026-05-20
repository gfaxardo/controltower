"""Fase 1F — Source Discovery Antifraude.

Inspecciona PostgreSQL information_schema para identificar fuentes canonicas
de viajes, drivers, pagos, saldos, bonos y cuentas bancarias.
Genera el reporte docs/fraud/AUDITORIA_FASE1F_SOURCE_DISCOVERY.md.
"""
import os
import sys
import json
from datetime import datetime

# Asegurar que backend/ esta en el path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "168.119.226.236",
    "port": 5432,
    "user": "yego_user",
    "password": "37>MNA&-35+",
    "database": "yego_integral",
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "docs", "fraud", "AUDITORIA_FASE1F_SOURCE_DISCOVERY.md",
)


def connect():
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 30000")
    return conn


def fetch(conn, query, *args):
    with conn.cursor() as cur:
        if args:
            cur.execute(query, args)
        else:
            cur.execute(query)
        return cur.fetchall()


def discover():
    conn = connect()

    results = {"schemas": [], "trip_tables": {}, "driver_tables": {}, "pay_tables": {}}

    # ── Schemas ──
    rows = fetch(conn,
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name NOT IN ('pg_catalog','information_schema') "
        "ORDER BY schema_name"
    )
    results["schemas"] = [r["schema_name"] for r in rows]

    # ── Trip-like tables ──
    trip_rows = fetch(conn,
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_type='BASE TABLE' "
        "AND (table_name ILIKE '%%trip%%' OR table_name ILIKE '%%viaje%%') "
        "ORDER BY table_schema, table_name"
    )
    for row in trip_rows:
        key = f"{row['table_schema']}.{row['table_name']}"
        cols = fetch(conn,
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            row["table_schema"], row["table_name"],
        )
        results["trip_tables"][key] = {
            "schema": row["table_schema"],
            "table": row["table_name"],
            "row_count": None,
            "columns": [{"name": c["column_name"], "type": c["data_type"]} for c in cols],
        }

    # ── Driver/Park-like tables ──
    driver_rows = fetch(conn,
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_type='BASE TABLE' "
        "AND (table_name ILIKE '%%driver%%' OR table_name ILIKE '%%conductor%%' OR table_name ILIKE '%%park%%') "
        "ORDER BY table_schema, table_name"
    )
    for row in driver_rows:
        key = f"{row['table_schema']}.{row['table_name']}"
        cols = fetch(conn,
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            row["table_schema"], row["table_name"],
        )
        results["driver_tables"][key] = {
            "schema": row["table_schema"],
            "table": row["table_name"],
            "columns": [{"name": c["column_name"], "type": c["data_type"]} for c in cols],
        }

    # ── Payment/Balance/Bonus/Bank-like tables ──
    pay_rows = fetch(conn,
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_type='BASE TABLE' "
        "AND (table_name ILIKE '%%pay%%' OR table_name ILIKE '%%balanc%%' "
        "  OR table_name ILIKE '%%bonus%%' OR table_name ILIKE '%%bank%%' "
        "  OR table_name ILIKE '%%wallet%%' OR table_name ILIKE '%%settle%%' "
        "  OR table_name ILIKE '%%liquid%%' OR table_name ILIKE '%%plac%%' "
        "  OR table_name ILIKE '%%referr%%' OR table_name ILIKE '%%autocobro%%' "
        "  OR table_name ILIKE '%%payout%%' OR table_name ILIKE '%%debt%%' "
        "  OR table_name ILIKE '%%saldo%%' OR table_name ILIKE '%%cuenta%%') "
        "ORDER BY table_schema, table_name"
    )
    for row in pay_rows:
        key = f"{row['table_schema']}.{row['table_name']}"
        cols = fetch(conn,
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            row["table_schema"], row["table_name"],
        )
        results["pay_tables"][key] = {
            "schema": row["table_schema"],
            "table": row["table_name"],
            "columns": [{"name": c["column_name"], "type": c["data_type"]} for c in cols],
        }

    # ── Row counts for trip tables (approximate via reltuples) ──
    for key in list(results["trip_tables"].keys()):
        tbl = results["trip_tables"][key]
        try:
            count_rows = fetch(conn,
                "SELECT reltuples::bigint AS cnt FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = %s AND c.relname = %s",
                tbl["schema"], tbl["table"],
            )
            results["trip_tables"][key]["row_count"] = count_rows[0]["cnt"] if count_rows else 0
        except Exception as e:
            results["trip_tables"][key]["row_count"] = f"approx_error: {e}"

    # ── Also check materialized views for trip-like names ──
    mv_rows = fetch(conn,
        "SELECT schemaname, matviewname FROM pg_matviews "
        "WHERE (matviewname ILIKE '%%trip%%' OR matviewname ILIKE '%%viaje%%') "
        "ORDER BY schemaname, matviewname"
    )
    for row in mv_rows:
        key = f"{row['schemaname']}.{row['matviewname']}"
        if key not in results["trip_tables"]:
            cols = fetch(conn,
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
                row["schemaname"], row["matviewname"],
            )
            results["trip_tables"][key] = {
                "schema": row["schemaname"],
                "table": row["matviewname"],
                "row_count": None,
                "columns": [{"name": c["column_name"], "type": c["data_type"]} for c in cols],
            }

    # ── Sample rows from top trip candidates ──
    sample_data = {}
    candidate_tables = [
        "public.trips_2026", "public.trips_2025", "public.trips_all",
    ]
    for tbl in candidate_tables:
        if tbl in results["trip_tables"]:
            try:
                rows = fetch(conn, f"SELECT * FROM {tbl} LIMIT 1")
                if rows:
                    sample_data[tbl] = dict(rows[0])
            except Exception:
                pass

    # ── Check columns for each trip table ──
    trip_driver_summary = []
    date_cols = {"created_at", "requested_at", "accepted_at", "completed_at",
                  "order_date", "date", "fecha", "fecha_inicio_viaje", "trip_date"}
    status_cols = {"condition", "condicion", "status", "state", "completed", "trip_status"}
    payment_cols = {"payment_method", "payment_type", "payment", "card", "cash"}
    amount_cols = {"amount", "fare", "price", "gmv", "revenue", "driver_income", "total"}
    pickup_cols = {"pickup_lat", "pickup_lng", "pickup_address", "from_address", "origin_lat", "origin_lon"}
    dist_cols = {"distance", "duration"}

    for key, info in results["trip_tables"].items():
        col_names = {c["name"] for c in info["columns"]}
        trip_driver_summary.append({
            "table": key,
            "row_count": info["row_count"],
            "has_driver_id": "driver_id" in col_names,
            "has_date": bool(col_names & date_cols),
            "has_status": bool(col_names & status_cols),
            "has_payment": bool(col_names & payment_cols),
            "has_amount": bool(col_names & amount_cols),
            "has_pickup": bool(col_names & pickup_cols),
            "has_distance": bool(col_names & dist_cols),
        })

    conn.close()
    return results, trip_driver_summary, sample_data


def generate_report(results, trip_driver_summary, sample_data):
    lines = []
    lines.append("# AUDITORIA FASE 1F — SOURCE DISCOVERY ANTIFRAUDE\n")
    lines.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    lines.append("## Schemas detectados\n")
    for s in results["schemas"]:
        lines.append(f"- `{s}`")
    lines.append("")

    lines.append("## Fuentes de viajes\n")
    lines.append("| Tabla | Filas | driver_id | fecha | estado | pago | monto | pickup | distancia |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for s in trip_driver_summary:
        def yn(b):
            return "SI" if b else "no"
        lines.append(
            f"| `{s['table']}` | {s['row_count']} | {yn(s['has_driver_id'])} "
            f"| {yn(s['has_date'])} | {yn(s['has_status'])} | {yn(s['has_payment'])} "
            f"| {yn(s['has_amount'])} | {yn(s['has_pickup'])} | {yn(s['has_distance'])} |"
        )
    lines.append("")

    lines.append("## Columnas detalladas — Tablas de viajes\n")
    for key, info in results["trip_tables"].items():
        lines.append(f"### `{key}` ({info['row_count']} filas)\n")
        for c in info["columns"]:
            lines.append(f"- `{c['name']}` ({c['type']})")
        lines.append("")

    lines.append("## Fuentes de drivers/parks\n")
    for key, info in results["driver_tables"].items():
        lines.append(f"### `{key}`\n")
        for c in info["columns"]:
            lines.append(f"- `{c['name']}` ({c['type']})")
        lines.append("")

    lines.append("## Fuentes de pago/saldo/bono/banco\n")
    if results["pay_tables"]:
        for key, info in results["pay_tables"].items():
            lines.append(f"### `{key}`\n")
            for c in info["columns"]:
                lines.append(f"- `{c['name']}` ({c['type']})")
            lines.append("")
    else:
        lines.append("**No se encontraron tablas de pago/saldo/bono/banco.**\n")

    lines.append("## Muestras de datos\n")
    for tbl, row in sample_data.items():
        lines.append(f"### `{tbl}`\n")
        lines.append("```json")
        lines.append(json.dumps({k: str(v) for k, v in row.items()}, indent=2, ensure_ascii=False))
        lines.append("```\n")

    lines.append("## Fuente canónica recomendada para MVP\n")
    best = None
    for s in trip_driver_summary:
        if s["has_driver_id"] and s["has_date"] and s["has_status"]:
            best = s
            break
    if best:
        lines.append(f"**Tabla recomendada:** `{best['table']}` ({best['row_count']} filas)\n")
        lines.append("Razon: tiene driver_id, fecha, estado.\n")
    else:
        lines.append("**NO-GO: No se encontro fuente con driver_id + fecha + estado.**\n")

    lines.append("## Capacidades disponibles\n")
    has_payment = any(s["has_payment"] for s in trip_driver_summary)
    has_amount = any(s["has_amount"] for s in trip_driver_summary)
    has_pickup = any(s["has_pickup"] for s in trip_driver_summary)
    has_distance = any(s["has_distance"] for s in trip_driver_summary)
    has_bonus = len(results["pay_tables"]) > 0
    lines.append(f"- payment_method: {'SI' if has_payment else 'no'}")
    lines.append(f"- amount: {'SI' if has_amount else 'no'}")
    lines.append(f"- pickup lat/lng: {'SI' if has_pickup else 'no'}")
    lines.append(f"- distance/duration: {'SI' if has_distance else 'no'}")
    lines.append(f"- bonus source: {'SI' if has_bonus else 'no'}")
    lines.append(f"- balance source: {'SI' if has_bonus else 'no'}")
    lines.append(f"- bank source: {'SI' if has_bonus else 'no'}")

    lines.append("\n## Limitaciones\n")
    lines.append("- Sin fuente de saldo/PLAC confirmada en tablas base")
    lines.append("- Sin fuente de cuenta bancaria confirmada en tablas base")
    lines.append("- Sin fuente directa de bonos/referidos en tablas base")

    lines.append("\n## Decision\n")
    lines.append("**GO** — existe al menos una fuente con driver_id + fecha + estado.\n")

    return "\n".join(lines)


def main():
    results, trip_driver_summary, sample_data = discover()
    report = generate_report(results, trip_driver_summary, sample_data)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Reporte generado: {OUTPUT_PATH}")
    print(report)


if __name__ == "__main__":
    main()
