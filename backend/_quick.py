# -*- coding: utf-8 -*-
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import os, json

with get_db() as conn:
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT COUNT(*) AS n FROM raw_yango.orders_raw WHERE park_id='08e20910d81d42658d4334d3f6d10ac0' AND order_created_at::date='2026-06-04'")
    print(f"Orders: {c.fetchone()['n']}")
    c.close()

cp = "exports/audits/yango_raw_landing/ingest_checkpoint.json"
if os.path.exists(cp):
    d = json.load(open(cp, "r", encoding="utf-8"))
    pages = d.get("completed_pages", {})
    print(f"Checkpoint pages: {len(pages)}")
    if pages:
        pnums = sorted([int(k.split("_")[-1]) for k in pages.keys()])
        print(f"Page range: {min(pnums)}-{max(pnums)}")

# Check if deep process still running
out = "exports/audits/yango_raw_landing/stdout_deep.txt"
if os.path.exists(out):
    lines = open(out).readlines()
    print(f"stdout lines: {len(lines)}")
    for l in lines[-5:]:
        print(f"  > {l.strip()}")
