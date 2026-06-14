"""
LG-CEMETERY-RULEGROUP-1O — DRAFT_003 Rule Group Consolidation (Idempotent)

Root cause: Recovery universes had split rule groups (entry + value_high/value_low).
The OR logic across groups allowed drivers to match Recovery based on value_tier alone,
ignoring inactivity requirements. Consolidates all rules to 'entry' group.

Idempotent. Safe to run multiple times. Does NOT touch ACTIVE configs.
"""
import psycopg2
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from app.db.connection import _get_connection_params

params = _get_connection_params()
c = psycopg2.connect(**params)
c.autocommit = True
cur = c.cursor()

# Target only DRAFT_003
cur.execute("SELECT version_id, version_code, status FROM growth.universe_config_version WHERE version_code='UNIVERSE_V2_DRAFT_003'")
ver = cur.fetchone()
if not ver:
    print("UNIVERSE_V2_DRAFT_003 not found. Nothing to fix.")
    cur.close(); c.close()
    sys.exit(0)

vid, vcode, vstatus = ver
print(f"Found {vcode} (status={vstatus}, id={vid})")

# Check current group count
cur.execute("SELECT universe_code, COUNT(DISTINCT rule_group) AS groups FROM growth.universe_rule_config WHERE version_id=%s GROUP BY universe_code HAVING COUNT(DISTINCT rule_group) > 1", (vid,))
multi = cur.fetchall()
if multi:
    print(f"\nBEFORE: {len(multi)} segments have multiple rule groups:")
    for r in multi: print(f"  {r[0]}: {r[1]} groups")

# Fix: consolidate all rules to 'entry' group
cur.execute("UPDATE growth.universe_rule_config SET rule_group='entry' WHERE version_id=%s", (vid,))
print(f"\nFIX: {cur.rowcount} rules consolidated to 'entry' group")

# Verify
cur.execute("SELECT universe_code, COUNT(DISTINCT rule_group) AS groups FROM growth.universe_rule_config WHERE version_id=%s GROUP BY universe_code HAVING COUNT(DISTINCT rule_group) > 1", (vid,))
remaining = cur.fetchall()
if remaining:
    print(f"WARNING: {len(remaining)} segments still have multiple groups!")
else:
    print("AFTER: All segments have exactly 1 rule group. Fix applied successfully.")

cur.close(); c.close()
print("\nScript complete. DRAFT_003 rule groups consolidated.")
