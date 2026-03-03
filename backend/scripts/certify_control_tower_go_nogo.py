#!/usr/bin/env python3
"""
Certificación Control Tower (Driver Lifecycle) — GO / CAUTION / NO-GO.
Ejecuta check completo, inspecciona columnas, mide 3 señales, emite veredicto.
Todo output a backend/logs/ct_go_nogo_YYYYMMDD_HHMM.log
Genera docs/CONTROL_TOWER_GO_NOGO.md

Uso: cd backend && python -m scripts.certify_control_tower_go_nogo
NO destructivo. Solo SET a nivel sesión si el check ya lo hace.
"""
from __future__ import annotations

import os
import re
import sys
import subprocess
from datetime import datetime, timezone
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
DOC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "CONTROL_TOWER_GO_NOGO.md"
)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _ts_file() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")


def run(log_file: object, msg: str) -> None:
    print(msg)
    if hasattr(log_file, "write"):
        log_file.write(msg + "\n")
        log_file.flush()


def main() -> int:
    os.makedirs(LOG_DIR, exist_ok=True)
    ts_file = _ts_file()
    log_path = os.path.join(LOG_DIR, f"ct_go_nogo_{ts_file}.log")
    log_buffer = StringIO()

    def log(msg: str = ""):
        run(log_buffer, msg)

    log("=" * 60)
    log("CONTROL TOWER (DRIVER LIFECYCLE) — CERTIFICACIÓN GO/NO-GO")
    log(f"Timestamp: {_ts()}")
    log(f"Log file: {log_path}")
    log("=" * 60)

    # ----- FASE 0 -----
    log("\n--- FASE 0: PREPARAR LOGS ---")
    log(f"Carpeta logs: {LOG_DIR} (existe: {os.path.isdir(LOG_DIR)})")
    log(f"Timestamp para archivo: {ts_file}")

    # ----- FASE 1: Check completo -----
    log("\n--- FASE 1: CHECK COMPLETO ---")
    check_script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "check_driver_lifecycle_and_validate.py"
    )
    if not os.path.isfile(check_script):
        log(f"NO EXISTE: {check_script}")
        check_pass = False
        check_output = "Script check_driver_lifecycle_and_validate.py no encontrado."
    else:
        log(f"Script encontrado: {check_script}")
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = os.environ.copy()
        if os.environ.get("CERTIFY_SKIP_REFRESH", "").strip().lower() in ("1", "true", "yes"):
            env["DRIVER_LIFECYCLE_REFRESH_MODE"] = "none"
            log("(CERTIFY_SKIP_REFRESH=1: refresh omitido, solo validaciones)")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.check_driver_lifecycle_and_validate"],
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=7200,
                env=env,
            )
            check_output = (result.stdout or "") + "\n" + (result.stderr or "")
            log(check_output)
            check_pass = result.returncode == 0
            if result.returncode != 0:
                log(f"PASS/FAIL: FAIL (exit code {result.returncode})")
            else:
                log("PASS/FAIL: PASS")
        except subprocess.TimeoutExpired:
            log("PASS/FAIL: FAIL (timeout)")
            check_output = "Timeout ejecutando check."
            check_pass = False
        except Exception as e:
            log(f"PASS/FAIL: FAIL (excepción: {e})")
            check_output = str(e)
            check_pass = False

    # ----- FASE 2: Inspección y 3 señales -----
    log("\n--- FASE 2: INSPECCIÓN Y 3 SEÑALES ---")

    mvs_list = []
    columns_list = []
    freshness_col = None
    park_id_exists = False
    max_last_completed_ts = None
    n_total = None
    n_null_park = None
    null_share = None
    distinct_parks = None
    db_error = None

    try:
        from app.db.connection import get_db, init_db_pool
        from psycopg2.extras import RealDictCursor

        init_db_pool()
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # 2.1 MVs en ops
            log("2.1 MVs en schema ops:")
            cur.execute("""
                SELECT schemaname, matviewname
                FROM pg_matviews
                WHERE schemaname = 'ops'
                ORDER BY 2
            """)
            mvs_list = [dict(r) for r in cur.fetchall()]
            for r in mvs_list:
                log(f"  {r.get('schemaname')}.{r.get('matviewname')}")

            # 2.2 Columnas reales (information_schema; fallback pg_catalog si vacío)
            log("\n2.2 Columnas (information_schema):")
            cur.execute("""
                SELECT table_name, column_name, data_type, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = 'ops'
                  AND table_name IN ('mv_driver_lifecycle_base', 'mv_driver_weekly_stats')
                ORDER BY table_name, ordinal_position
            """)
            columns_list = [dict(r) for r in cur.fetchall()]
            if not columns_list:
                log("  (vacío; intentando pg_catalog)")
                cur.execute("""
                    SELECT c.relname AS table_name, a.attname AS column_name,
                           pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                           a.attnum AS ordinal_position
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
                    WHERE n.nspname = 'ops'
                      AND c.relname IN ('mv_driver_lifecycle_base', 'mv_driver_weekly_stats')
                      AND a.attnum > 0 AND NOT a.attisdropped
                    ORDER BY c.relname, a.attnum
                """)
                columns_list = [dict(r) for r in cur.fetchall()]
            for r in columns_list:
                log(f"  {r.get('table_name')} | {r.get('column_name')} | {r.get('data_type')}")

            base_cols = [r["column_name"] for r in columns_list if r.get("table_name") == "mv_driver_lifecycle_base"]
            stats_cols = [r["column_name"] for r in columns_list if r.get("table_name") == "mv_driver_weekly_stats"]

            if "last_completed_ts" in base_cols:
                freshness_col = "last_completed_ts"
            else:
                for alt in ("updated_at", "period_end", "last_trip_ts", "last_completed_at"):
                    if alt in base_cols:
                        freshness_col = alt
                        break
            park_id_exists = "park_id" in stats_cols

            # 2.3 Señal A — Freshness
            log("\n2.3 Señal A — Freshness:")
            if freshness_col:
                cur.execute(
                    f"SELECT MAX({freshness_col}) AS max_ts FROM ops.mv_driver_lifecycle_base"
                )
                row = cur.fetchone()
                max_last_completed_ts = row.get("max_ts") if row else None
                log(f"  Query: SELECT MAX({freshness_col}) FROM ops.mv_driver_lifecycle_base")
                log(f"  Resultado: {max_last_completed_ts}")
            else:
                log("  NO MEDIBLE FRESHNESS con columnas actuales (no last_completed_ts ni alternativa).")

            # 2.4 Señal B — Park null share
            log("\n2.4 Señal B — Park null share:")
            if park_id_exists:
                cur.execute("""
                    SELECT
                        COUNT(*) AS n,
                        COUNT(*) FILTER (WHERE park_id IS NULL) AS n_null_park,
                        (COUNT(*) FILTER (WHERE park_id IS NULL)::float / NULLIF(COUNT(*), 0)) AS null_share
                    FROM ops.mv_driver_weekly_stats
                """)
                row = cur.fetchone()
                if row:
                    n_total = row.get("n")
                    n_null_park = row.get("n_null_park")
                    null_share = row.get("null_share")
                log("  Query: COUNT(*), COUNT(*) FILTER (WHERE park_id IS NULL), null_share")
                log(f"  Resultado: n={n_total}, n_null_park={n_null_park}, null_share={null_share}")
            else:
                log("  NO MEDIBLE park null share (park_id no existe en mv_driver_weekly_stats).")

            # 2.5 Señal C — Coverage parks
            log("\n2.5 Señal C — Coverage (distinct parks):")
            if park_id_exists:
                cur.execute(
                    "SELECT COUNT(DISTINCT park_id) AS distinct_parks FROM ops.mv_driver_weekly_stats"
                )
                row = cur.fetchone()
                distinct_parks = row.get("distinct_parks") if row else None
                log(f"  Resultado: distinct_parks={distinct_parks}")
            else:
                log("  NO MEDIBLE (park_id no existe).")

            cur.close()

    except Exception as e:
        db_error = str(e)
        log(f"Error DB (FASE 2): {db_error}")
        if not mvs_list and not columns_list:
            log("  No se pudo inspeccionar MVs ni columnas.")

    # ----- FASE 3: Veredicto -----
    log("\n--- FASE 3: VEREDICTO ---")

    FRESHNESS_GO_HOURS = 24
    FRESHNESS_CAUTION_HOURS = 48
    NULL_SHARE_NOGO = 0.05
    NULL_SHARE_CAUTION = 0.01

    delta_h = None
    if max_last_completed_ts is not None:
        try:
            now = datetime.now(timezone.utc)
            ts_utc = max_last_completed_ts
            if getattr(ts_utc, "tzinfo", None) is None:
                ts_utc = ts_utc.replace(tzinfo=timezone.utc)
            delta_h = (now - ts_utc).total_seconds() / 3600
        except Exception:
            pass

    verdict = "NO-GO"
    reasons = []

    if db_error and not check_pass:
        reasons.append("Check falló y no se pudo conectar a DB.")
    elif db_error:
        reasons.append(f"Error DB en FASE 2: {db_error}; veredicto basado en check y datos disponibles.")
    if not check_pass:
        reasons.append("El check completo (refresh + validaciones) falló o no se ejecutó.")
    if freshness_col is None and not db_error:
        reasons.append("Freshness no es medible (no hay columna utilizable).")
    if delta_h is not None:
        if delta_h > FRESHNESS_CAUTION_HOURS:
            reasons.append(f"Freshness muy antiguo (> {FRESHNESS_CAUTION_HOURS}h).")
        elif delta_h > FRESHNESS_GO_HOURS:
            reasons.append(f"Freshness entre {FRESHNESS_GO_HOURS}h y {FRESHNESS_CAUTION_HOURS}h.")
    if null_share is not None:
        if null_share >= NULL_SHARE_NOGO:
            reasons.append(f"null_share >= {NULL_SHARE_NOGO*100:.0f}%.")
        elif null_share >= NULL_SHARE_CAUTION:
            reasons.append(f"null_share entre {NULL_SHARE_CAUTION*100:.0f}% y <{NULL_SHARE_NOGO*100:.0f}%.")
    if distinct_parks is not None and distinct_parks == 0:
        reasons.append("distinct_parks = 0 (sin cobertura).")

    # Reglas explícitas
    if not check_pass:
        verdict = "NO-GO"
    elif freshness_col is None and not db_error:
        verdict = "NO-GO"
    elif null_share is not None and null_share >= NULL_SHARE_NOGO:
        verdict = "NO-GO"
    elif distinct_parks is not None and distinct_parks == 0:
        verdict = "NO-GO"
    elif delta_h is not None and delta_h > FRESHNESS_CAUTION_HOURS:
        verdict = "NO-GO"
    elif delta_h is not None and delta_h > FRESHNESS_GO_HOURS:
        verdict = "CAUTION"
    elif null_share is not None and null_share >= NULL_SHARE_CAUTION:
        verdict = "CAUTION"
    elif delta_h is not None and delta_h <= FRESHNESS_GO_HOURS and (null_share is None or null_share < NULL_SHARE_CAUTION) and (distinct_parks is None or distinct_parks > 0):
        verdict = "GO"
        reasons = []
    elif db_error:
        verdict = "NO-GO"
    else:
        verdict = "CAUTION"
        if not reasons:
            reasons.append("Datos incompletos o no medibles.")

    log(f"Veredicto: {verdict}")
    for r in reasons:
        log(f"  - {r}")
    log("\nValores exactos:")
    log(f"  check_pass={check_pass}, freshness_col={freshness_col}, max_last_completed_ts={max_last_completed_ts}")
    log(f"  n_total={n_total}, n_null_park={n_null_park}, null_share={null_share}, distinct_parks={distinct_parks}")

    # Escribir log a disco
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(log_buffer.getvalue())
    run(log_buffer, f"\nLog guardado en: {log_path}")

    # ----- FASE 4: Doc final -----
    os.makedirs(os.path.dirname(DOC_PATH), exist_ok=True)
    doc_lines = [
        "# Control Tower (Driver Lifecycle) — GO / NO-GO",
        "",
        f"**Fecha certificación:** {_ts()}",
        f"**Log:** `backend/logs/ct_go_nogo_{ts_file}.log`",
        "",
        "## 1) Resumen ejecutivo",
        "",
        f"- **Veredicto:** {verdict}",
        f"- Check completo: {'PASS' if check_pass else 'FAIL'}.",
        f"- Freshness: columna={freshness_col}, MAX(ts)={max_last_completed_ts}.",
        f"- Park null share: {null_share} ({n_null_park}/{n_total} filas con park_id NULL)." if null_share is not None else "- Park null share: NO MEDIBLE.",
        f"- Parks distintos: {distinct_parks}." if distinct_parks is not None else "- Parks distintos: NO MEDIBLE.",
        "",
        "## 2) Evidencia",
        "",
        "### Comando ejecutado",
        "```",
        "cd backend && python -m scripts.check_driver_lifecycle_and_validate",
        "```",
        "",
        "### Resultado del check",
        "```",
        (check_output[:4000] + "\n... (truncado)") if check_output and len(check_output) > 4000 else (check_output or "(sin salida)"),
        "```",
        "",
        "### MVs detectadas (schema ops)",
        "",
    ]
    for r in mvs_list:
        doc_lines.append(f"- {r.get('schemaname')}.{r.get('matviewname')}")
    if not mvs_list:
        doc_lines.append("- (ninguna o error de conexión)")
    doc_lines.extend([
        "",
        "### Columnas detectadas (mv_driver_lifecycle_base, mv_driver_weekly_stats)",
        "",
    ])
    for r in columns_list:
        doc_lines.append(f"- {r.get('table_name')} | {r.get('column_name')} | {r.get('data_type')}")
    if not columns_list:
        doc_lines.append("- (ninguna o error de conexión)")
    doc_lines.extend([
        "",
        "### Señales",
        "",
        "| Señal | Query / Nota | Resultado |",
        "|-------|--------------|-----------|",
    ])
    doc_lines.append(f"| A Freshness | MAX({freshness_col or 'N/A'}) FROM ops.mv_driver_lifecycle_base | {max_last_completed_ts} |")
    doc_lines.append(f"| B Park null share | COUNT FILTER park_id IS NULL / COUNT(*) | n_null={n_null_park}, total={n_total}, share={null_share} |")
    doc_lines.append(f"| C Distinct parks | COUNT(DISTINCT park_id) FROM ops.mv_driver_weekly_stats | {distinct_parks} |")
    doc_lines.extend([
        "",
        "## 3) Recomendación inmediata",
        "",
    ])
    if verdict == "NO-GO":
        doc_lines.extend([
            "- **Acciones correctivas sugeridas (no destructivas):**",
            "  1. Revisar conectividad y credenciales de BD; ejecutar `python -m scripts.check_driver_lifecycle_and_validate --diagnose`.",
            "  2. Revisar timeouts/locks (statement_timeout, lock_timeout) y ejecutar refresh en ventana de bajo uso.",
            "  3. Si park_id NULL es alto, revisar calidad de datos en origen (trips_all, drivers) y pipeline de asignación de park.",
            "",
        ])
    elif verdict == "CAUTION":
        doc_lines.extend([
            "- Usar para exploración; no para decisiones críticas hasta mejorar freshness o reducir null_share.",
            "- Mitigar: programar refresh más frecuente; investigar causas de park_id NULL.",
            "",
        ])
    else:
        doc_lines.extend([
            "- Operar con normalidad. Revalidar periódicamente (ej. semanal o tras cada refresh): ejecutar de nuevo este script de certificación.",
            "",
        ])
    doc_lines.append("---")
    doc_lines.append(f"*Generado por scripts/certify_control_tower_go_nogo.py — {_ts()}*")

    with open(DOC_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_lines))

    run(log_buffer, f"Doc guardado en: {DOC_PATH}")

    # Salida final a stdout para el usuario
    print(f"\n--- CERTIFICACIÓN COMPLETADA ---")
    print(f"Log: {log_path}")
    print(f"Doc: {DOC_PATH}")
    print(f"Veredicto: {verdict}")

    return 0 if verdict == "GO" else (1 if verdict == "CAUTION" else 2)


if __name__ == "__main__":
    sys.exit(main())
