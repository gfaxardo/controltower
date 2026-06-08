"""OV2-F.2B — Safe Batch Week Fact Recovery
Runs week_fact refresh in 30-day batches to avoid DB saturation.
Usage: python -m scripts.recover_week_fact_batched"""

import sys, os, subprocess, time
from datetime import date as dt_date, timedelta

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH_DAYS = 30
START_DATE = dt_date(2026, 4, 1)
END_DATE = dt_date(2026, 6, 8)

def run_refresh(start, end):
    cmd = [
        sys.executable, "-m", "scripts.refresh_omniview_real_slice_incremental",
        "--start-date", start.isoformat(),
        "--end-date", end.isoformat(),
        "--grain", "week",
        "--force",
    ]
    print(f"\n{'='*60}")
    print(f"BATCH: {start} -> {end} ({cmd[-1]})")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=BACKEND_DIR, capture_output=False, timeout=600)
    return result.returncode == 0

def main():
    print("OV2-F.2B SAFE BATCH WEEK RECOVERY")
    print(f"Range: {START_DATE} -> {END_DATE}")
    print(f"Batch size: {BATCH_DAYS} days")

    current = START_DATE
    batch_num = 1
    success = True

    while current < END_DATE:
        batch_end = min(current + timedelta(days=BATCH_DAYS), END_DATE)
        ok = run_refresh(current, batch_end)
        if not ok:
            print(f"BATCH {batch_num} FAILED at {current} -> {batch_end}")
            success = False
            break
        batch_num += 1
        current = batch_end
        time.sleep(2)

    if success:
        print(f"\nALL {batch_num - 1} BATCHES COMPLETED SUCCESSFULLY")
    else:
        print(f"\nRECOVERY INCOMPLETE — batch {batch_num} failed")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
