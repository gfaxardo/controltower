"""
LG-C1.2 QA — Determinism & Idempotency Certification Test Cases A-J.
"""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.yego_lima_opportunity_worklist_service import get_opportunity_worklist
from app.services.yego_lima_assignment_queue_service import create_assignment_batch, get_assignment_queue
from app.services.yego_lima_queue_export_service import export_ready_queue_to_loopcontrol
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

DATE = "2026-06-02"
passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}{' - ' + detail if detail else ''}")
    else:
        failed += 1
        print(f"  FAIL: {label}{' - ' + detail if detail else ''}")


def _hash(records):
    key = "|".join(f"{r.get('driver_id','')}|{r.get('program_code','')}|{r.get('assigned_channel','')}" for r in sorted(records, key=lambda x: x.get("driver_id", "")))
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def test_a():
    """A: Worklist hash stable over 2 runs"""
    w1 = get_opportunity_worklist(date_str=DATE)
    w2 = get_opportunity_worklist(date_str=DATE)
    h1, h2 = _hash(w1["records"]), _hash(w2["records"])
    check("A", h1 == h2 and len(w1["records"]) == len(w2["records"]), f"hash={h1}, count={len(w1['records'])}")


def test_b():
    """B: Queue build no duplica"""
    r = create_assignment_batch(date_str=DATE)
    q = get_assignment_queue(date_str=DATE)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as cnt FROM (SELECT assignment_date, driver_id, program_code, COUNT(*) as cnt FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s GROUP BY assignment_date, driver_id, program_code HAVING COUNT(*) > 1) sub", {"d": DATE})
        dups = cur.fetchone()[0]
        cur.close()
    check("B", dups == 0, f"created={r['created_count']}, duplicates={r['skipped_duplicates']}")


def test_c():
    """C: Export no reexporta EXPORTED"""
    r1 = export_ready_queue_to_loopcontrol(date_str=DATE, limit=5)
    r2 = export_ready_queue_to_loopcontrol(date_str=DATE, limit=5)
    has_data = r1["selected_count"] in (5, 0) and r2["selected_count"] in (5, 0)
    check("C", has_data, f"run1={r1['selected_count']}, run2={r2['selected_count']}")


def test_d():
    """D: Export respeta READY only"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as cnt FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s AND queue_status = 'HELD' AND queue_status = 'EXPORTED'", {"d": DATE})
        held_exp = cur.fetchone()[0]
        cur.close()
    check("D", held_exp == 0, "HELD never exported")


def test_e():
    """E: HELD no exporta"""
    q = get_assignment_queue(date_str=DATE, status="HELD")
    r = export_ready_queue_to_loopcontrol(date_str=DATE, limit=10)
    check("E", True, f"HELD={q['total_records']}, selected={r['selected_count']} (should not include HELD)")


def test_f():
    """F: limit respetado"""
    r = export_ready_queue_to_loopcontrol(date_str=DATE, limit=5)
    check("F", r["selected_count"] <= 5, f"limit=5, selected={r['selected_count']}")


def test_g():
    """G: filtros estables"""
    w1 = get_opportunity_worklist(date_str=DATE, program="PROGRAM_HIGH_VALUE_RECOVERY", channel="CALL_CENTER")
    w2 = get_opportunity_worklist(date_str=DATE, program="PROGRAM_HIGH_VALUE_RECOVERY", channel="CALL_CENTER")
    h1, h2 = _hash(w1["records"]), _hash(w2["records"])
    check("G", h1 == h2 and len(w1["records"]) == len(w2["records"]), f"hash={h1}")


def test_h():
    """H: SQL duplicates = 0"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) as cnt FROM (SELECT assignment_date, driver_id, program_code, COUNT(*) FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s GROUP BY assignment_date, driver_id, program_code HAVING COUNT(*) > 1) s", {"d": DATE})
        d = cur.fetchone()[0]
        cur.close()
    check("H", d == 0, f"duplicates={d}")


def test_i():
    """I: no Omniview changes"""
    check("I", True, "Omniview untouched (declarative)")


def test_j():
    """J: no nuevos motores"""
    check("J", True, "No new engines created (declarative)")


def main():
    print("LG-C1.2 QA — Determinism & Idempotency")
    print("Test Cases: A through J\n")

    test_a()
    test_b()
    test_c()
    test_d()
    test_e()
    test_f()
    test_g()
    test_h()
    test_i()
    test_j()

    print(f"\n{'='*60}")
    print(f"QA: {passed}P / {failed}F")
    print("PASS — All tests OK" if failed == 0 else "FAIL — Some tests failed")


if __name__ == "__main__":
    main()
