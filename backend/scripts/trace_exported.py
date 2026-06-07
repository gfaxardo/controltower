import sys, os, csv
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "exports", "audits", "lima_growth")
os.makedirs(EXPORT_DIR, exist_ok=True)
date_str = "2026-06-02"

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(f"""
        SELECT driver_id, driver_name, phone, program_code, program_name,
               assigned_channel, queue_status, campaign_id_external,
               export_batch_id, exported_at, opportunity_reason
        FROM growth.yego_lima_assignment_queue
        WHERE assignment_date = %(d)s AND queue_status = 'EXPORTED'
        ORDER BY priority_rank ASC, driver_name ASC
        LIMIT 10
    """, {"d": date_str})
    rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        print("No exported records found.")
        cur.close()
        exit(1)

    print(f"Traced {len(rows)} exported drivers:\n")
    for i, r in enumerate(rows, 1):
        phone = r.get("phone") or "N/A"
        name = r.get("driver_name", "N/A")[:30]
        prog = (r.get("program_code") or "").replace("PROGRAM_", "")
        ch = r.get("assigned_channel", "N/A")
        st = r.get("queue_status")
        exp = str(r.get("campaign_id_external") or "N/A")[:16]
        batch = str(r.get("export_batch_id") or "")[:8]
        print(f"  {i:2d}. {name:<30s} | phone={phone:<15s} | prog={prog:<20s} | ch={ch:<15s} | {st} | campaign={exp} | batch={batch}")

    # Write CSV
    csv_path = os.path.join(EXPORT_DIR, f"queue_export_trace_{datetime.now().strftime('%Y%m%d')}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV written: {csv_path}")

    # Write MD
    md_path = os.path.join(EXPORT_DIR, f"queue_export_trace_{datetime.now().strftime('%Y%m%d')}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# LC-1.5 Queue Export Trace — {date_str}\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("| # | Driver | Phone | Program | Channel | Status | Campaign |\n")
        f.write("|---|--------|-------|---------|---------|--------|----------|\n")
        for i, r in enumerate(rows, 1):
            f.write(f"| {i} | {r['driver_name'][:25]} | {r.get('phone','N/A')} | {(r.get('program_code','') or '').replace('PROGRAM_','')[:20]} | {r.get('assigned_channel','N/A')} | {r['queue_status']} | {str(r.get('campaign_id_external') or 'N/A')[:16]} |\n")
    print(f"MD written: {md_path}")

    cur.close()
