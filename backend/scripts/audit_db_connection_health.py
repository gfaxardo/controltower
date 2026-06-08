#!/usr/bin/env python3
"""
OV2-H.1 — DB Connection Health Audit
Audits PostgreSQL connection pool health: max connections, current usage,
connections by state, idle, blocked, long-running queries, locks.

Output:
  backend/exports/audits/infrastructure_health/db_connection_health.json
  backend/exports/audits/infrastructure_health/db_connection_health.md
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db_audit

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "infrastructure_health",
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

TIMESTAMP = datetime.now(timezone.utc).isoformat()


def _fetch_simple(conn, query: str) -> list:
    """Fetch all rows from a query. Returns list of tuples (raw cursor)."""
    cur = conn.cursor()
    try:
        cur.execute(query)
        return cur.fetchall()
    finally:
        cur.close()


def _fetch_dict(conn, query: str) -> list:
    from psycopg2.extras import RealDictCursor
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(query)
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            rows.append(d)
        return rows
    finally:
        cur.close()


def _fetch_value(conn, query: str, default=None):
    cur = conn.cursor()
    try:
        cur.execute(query)
        row = cur.fetchone()
        if row and row[0] is not None:
            return row[0]
    except Exception:
        pass
    finally:
        cur.close()
    return default


def audit_db_health() -> dict:
    report = {
        "audit_type": "db_connection_health",
        "generated_at": TIMESTAMP,
        "sections": {},
    }

    try:
        with get_db_audit() as conn:
            conn.autocommit = True

            # 1) max_connections
            max_conn = _fetch_value(conn, "SHOW max_connections;")
            report["sections"]["max_connections"] = int(max_conn) if max_conn else None

            # 2) current connections
            current = _fetch_value(
                conn,
                "SELECT COUNT(*) FROM pg_stat_activity WHERE backend_type='client backend';"
            )
            report["sections"]["current_connections"] = int(current) if current is not None else None

            # 3) connections by state
            by_state = _fetch_dict(conn, """
                SELECT state, COUNT(*) AS count
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
                GROUP BY state
                ORDER BY count DESC
            """)
            report["sections"]["connections_by_state"] = by_state

            # 4) connections by application_name (top 20)
            by_app = _fetch_dict(conn, """
                SELECT
                    COALESCE(application_name, '(unset)') AS application_name,
                    COUNT(*) AS count
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
                GROUP BY application_name
                ORDER BY count DESC
                LIMIT 20
            """)
            report["sections"]["connections_by_application_name"] = by_app

            # 5) idle connections
            idle_count = _fetch_value(conn, """
                SELECT COUNT(*) FROM pg_stat_activity
                WHERE backend_type = 'client backend' AND state = 'idle'
            """)
            report["sections"]["idle_connections"] = int(idle_count) if idle_count is not None else None

            # 6) idle in transaction (dangerous)
            idle_in_txn = _fetch_dict(conn, """
                SELECT
                    pid,
                    usename,
                    application_name,
                    state,
                    state_change::text AS state_change,
                    query_start::text AS query_start,
                    xact_start::text AS xact_start,
                    LEFT(query, 200) AS query_preview
                FROM pg_stat_activity
                WHERE backend_type = 'client backend' AND state = 'idle in transaction'
                ORDER BY xact_start ASC NULLS LAST
            """)
            report["sections"]["idle_in_transaction"] = idle_in_txn

            # 7) longest running queries (top 10)
            long_running = _fetch_dict(conn, """
                SELECT
                    pid,
                    usename,
                    application_name,
                    state,
                    query_start::text AS query_start,
                    EXTRACT(EPOCH FROM (now() - query_start))::int AS elapsed_seconds,
                    LEFT(query, 300) AS query_preview
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
                  AND state = 'active'
                  AND query_start IS NOT NULL
                  AND wait_event_type IS DISTINCT FROM 'Activity'
                ORDER BY query_start ASC
                LIMIT 10
            """)
            report["sections"]["longest_running_queries"] = long_running

            # 8) blocked queries (waiting on locks)
            blocked = _fetch_dict(conn, """
                SELECT
                    blocked.pid AS blocked_pid,
                    blocked.usename AS blocked_user,
                    blocking.pid AS blocking_pid,
                    blocking.usename AS blocking_user,
                    blocked.query_start::text AS blocked_query_start,
                    EXTRACT(EPOCH FROM (now() - blocked.query_start))::int AS blocked_seconds,
                    LEFT(blocked.query, 200) AS blocked_query_preview,
                    LEFT(blocking.query, 200) AS blocking_query_preview
                FROM pg_stat_activity AS blocked
                JOIN pg_locks AS blocked_locks ON blocked.pid = blocked_locks.pid AND NOT blocked_locks.granted
                JOIN pg_locks AS blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
                    AND blocked_locks.database = blocking_locks.database
                    AND blocked_locks.relation = blocking_locks.relation
                    AND blocked_locks.pid != blocking_locks.pid
                    AND blocking_locks.granted
                JOIN pg_stat_activity AS blocking ON blocking.pid = blocking_locks.pid
                WHERE blocked.backend_type = 'client backend'
            """)
            report["sections"]["blocked_queries"] = blocked

            # 9) lock summary
            locks = _fetch_dict(conn, """
                SELECT
                    locktype,
                    mode,
                    COUNT(*) AS count,
                    COUNT(*) FILTER (WHERE granted) AS granted,
                    COUNT(*) FILTER (WHERE NOT granted) AS waiting
                FROM pg_locks
                GROUP BY locktype, mode
                ORDER BY count DESC
                LIMIT 20
            """)
            report["sections"]["locks_summary"] = locks

            # 10) oldest backend_start
            oldest_backend = _fetch_dict(conn, """
                SELECT
                    pid,
                    usename,
                    application_name,
                    state,
                    backend_start::text AS backend_start,
                    EXTRACT(EPOCH FROM (now() - backend_start))::int / 3600 AS hours_connected
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
                ORDER BY backend_start ASC
                LIMIT 5
            """)
            report["sections"]["oldest_backend_start"] = oldest_backend

            # 11) oldest xact_start (open transactions)
            oldest_xact = _fetch_dict(conn, """
                SELECT
                    pid,
                    usename,
                    application_name,
                    state,
                    xact_start::text AS xact_start,
                    EXTRACT(EPOCH FROM (now() - xact_start))::int AS open_seconds,
                    LEFT(query, 200) AS query_preview
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
                  AND xact_start IS NOT NULL
                ORDER BY xact_start ASC
                LIMIT 5
            """)
            report["sections"]["oldest_xact_start"] = oldest_xact

            # 12) oldest query_start (queries active longest)
            oldest_query = _fetch_dict(conn, """
                SELECT
                    pid,
                    usename,
                    application_name,
                    state,
                    query_start::text AS query_start,
                    EXTRACT(EPOCH FROM (now() - query_start))::int AS active_seconds,
                    LEFT(query, 200) AS query_preview
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
                  AND query_start IS NOT NULL
                ORDER BY query_start ASC
                LIMIT 5
            """)
            report["sections"]["oldest_query_start"] = oldest_query

            # 13) wait events summary
            wait_events = _fetch_dict(conn, """
                SELECT
                    wait_event_type,
                    wait_event,
                    COUNT(*) AS count
                FROM pg_stat_activity
                WHERE backend_type = 'client backend'
                  AND wait_event_type IS NOT NULL
                  AND wait_event IS NOT NULL
                GROUP BY wait_event_type, wait_event
                ORDER BY count DESC
                LIMIT 15
            """)
            report["sections"]["wait_events"] = wait_events

    except Exception as e:
        report["error"] = str(e)
        report["sections"]["connection_successful"] = False
    else:
        report["sections"]["connection_successful"] = True

    return report


def _generate_md(report: dict) -> str:
    s = report.get("sections", {})
    lines = [
        "# DB Connection Health Audit",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Connection successful:** {s.get('connection_successful', 'ERROR')}",
        "",
        "---",
        "",
        "## Connection Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| max_connections | {s.get('max_connections', '?')} |",
        f"| current_connections | {s.get('current_connections', '?')} |",
        f"| idle_connections | {s.get('idle_connections', '?')} |",
        f"| usage_pct | {_usage_pct(s):.1f}% |",
        "",
        "---",
        "",
        "## Connections by State",
        "",
    ]
    rows = s.get("connections_by_state", [])
    if rows:
        lines.append("| State | Count |")
        lines.append("|-------|-------|")
        for r in rows:
            lines.append(f"| {r.get('state', '?')} | {r.get('count', '?')} |")
    else:
        lines.append("*(no data)*")

    lines += [
        "",
        "---",
        "",
        "## Connections by Application Name",
        "",
    ]
    rows = s.get("connections_by_application_name", [])
    if rows:
        lines.append("| Application Name | Count |")
        lines.append("|------------------|-------|")
        for r in rows:
            lines.append(f"| {r.get('application_name', '?')} | {r.get('count', '?')} |")
    else:
        lines.append("*(no data)*")

    lines += [
        "",
        "---",
        "",
        "## Idle in Transaction (RISK)",
        "",
    ]
    rows = s.get("idle_in_transaction", [])
    if rows:
        lines.append(f"**{len(rows)} connection(s) idle in transaction** — DANGER: these hold locks")
        lines.append("")
        lines.append("| PID | User | App | Query Preview |")
        lines.append("|-----|------|-----|---------------|")
        for r in rows:
            lines.append(f"| {r.get('pid')} | {r.get('usename')} | {r.get('application_name')} | {r.get('query_preview', '')[:80]} |")
    else:
        lines.append("None — OK")

    lines += [
        "",
        "---",
        "",
        "## Longest Running Queries (Top 10)",
        "",
    ]
    rows = s.get("longest_running_queries", [])
    if rows:
        lines.append("| PID | User | State | Elapsed (s) | Query Preview |")
        lines.append("|-----|------|-------|-------------|---------------|")
        for r in rows:
            lines.append(f"| {r.get('pid')} | {r.get('usename')} | {r.get('state')} | {r.get('elapsed_seconds')} | {r.get('query_preview', '')[:80]} |")
    else:
        lines.append("None — OK")

    lines += [
        "",
        "---",
        "",
        "## Blocked Queries",
        "",
    ]
    rows = s.get("blocked_queries", [])
    if rows:
        lines.append(f"**{len(rows)} blocked query/ies** — risk of cascading timeouts")
        lines.append("")
        lines.append("| Blocked PID | Blocked User | Blocking PID | Blocking User | Blocked Seconds | Query Preview |")
        lines.append("|-------------|-------------|--------------|--------------|----------------|---------------|")
        for r in rows:
            lines.append(f"| {r.get('blocked_pid')} | {r.get('blocked_user')} | {r.get('blocking_pid')} | {r.get('blocking_user')} | {r.get('blocked_seconds')} | {r.get('blocked_query_preview', '')[:60]} |")
    else:
        lines.append("None — OK")

    lines += [
        "",
        "---",
        "",
        "## Lock Summary",
        "",
    ]
    rows = s.get("locks_summary", [])
    if rows:
        lines.append("| Lock Type | Mode | Total | Granted | Waiting |")
        lines.append("|-----------|------|-------|---------|---------|")
        for r in rows:
            lines.append(f"| {r.get('locktype')} | {r.get('mode')} | {r.get('count')} | {r.get('granted')} | {r.get('waiting')} |")
    else:
        lines.append("*(no data)*")

    lines += [
        "",
        "---",
        "",
        "## Oldest Backend Connections",
        "",
    ]
    rows = s.get("oldest_backend_start", [])
    if rows:
        lines.append("| PID | User | App | State | Hours Connected |")
        lines.append("|-----|------|-----|-------|-----------------|")
        for r in rows:
            lines.append(f"| {r.get('pid')} | {r.get('usename')} | {r.get('application_name')} | {r.get('state')} | {r.get('hours_connected')} |")
    else:
        lines.append("*(no data)*")

    lines += [
        "",
        "---",
        "",
        "## Oldest Open Transactions",
        "",
    ]
    rows = s.get("oldest_xact_start", [])
    if rows:
        lines.append("| PID | User | Open Seconds | Query Preview |")
        lines.append("|-----|------|-------------|---------------|")
        for r in rows:
            lines.append(f"| {r.get('pid')} | {r.get('usename')} | {r.get('open_seconds')} | {r.get('query_preview', '')[:60]} |")
    else:
        lines.append("None — OK")

    lines += [
        "",
        "---",
        "",
        "## Oldest Active Queries",
        "",
    ]
    rows = s.get("oldest_query_start", [])
    if rows:
        lines.append("| PID | User | Active Seconds | Query Preview |")
        lines.append("|-----|------|---------------|---------------|")
        for r in rows:
            lines.append(f"| {r.get('pid')} | {r.get('usename')} | {r.get('active_seconds')} | {r.get('query_preview', '')[:60]} |")
    else:
        lines.append("None — OK")

    lines += [
        "",
        "---",
        "",
        "## Wait Events",
        "",
    ]
    rows = s.get("wait_events", [])
    if rows:
        lines.append("| Wait Type | Event | Count |")
        lines.append("|-----------|-------|-------|")
        for r in rows:
            lines.append(f"| {r.get('wait_event_type')} | {r.get('wait_event')} | {r.get('count')} |")
    else:
        lines.append("*(no data)*")

    if report.get("error"):
        lines += [
            "",
            "---",
            "",
            f"**ERROR:** {report['error']}",
        ]

    return "\n".join(lines)


def _usage_pct(sections: dict) -> float:
    max_c = sections.get("max_connections", 0) or 1
    cur_c = sections.get("current_connections", 0) or 0
    return (cur_c / max_c) * 100 if max_c else 0


def main() -> int:
    print("[OV2-H.1] Auditing DB connection health...")
    report = audit_db_health()

    json_path = os.path.join(OUTPUT_DIR, "db_connection_health.json")
    md_path = os.path.join(OUTPUT_DIR, "db_connection_health.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    md_content = _generate_md(report)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")

    s = report.get("sections", {})
    print(f"  max_connections={s.get('max_connections')} current={s.get('current_connections')} idle={s.get('idle_connections')}")
    print(f"  usage={_usage_pct(s):.1f}% idle_in_txn={len(s.get('idle_in_transaction', []))} blocked={len(s.get('blocked_queries', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
