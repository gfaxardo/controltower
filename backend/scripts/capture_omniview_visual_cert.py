"""
O4.1 — Omniview Browser Visual Certification Script
Captura 15 screenshots via Playwright Chromium.
"""
import os, sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "omniview" / "visual_certification" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = os.environ.get("OMNIVIEW_URL", "http://localhost:5173")

GRAINS = ["daily", "weekly", "monthly"]
METRICS = {
    "trips": "trips_completed",
    "revenue": "revenue_yego_net",
    "drivers": "active_drivers",
    "ticket": "avg_ticket",
    "tpd": "trips_per_driver",
}

def capture():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        for grain in GRAINS:
            for metric_label, metric_key in METRICS.items():
                url = f"{BASE_URL}/?tab=omniview&grain={grain}&kpi={metric_key}"
                filename = f"{grain}_{metric_label}.png"
                filepath = OUT_DIR / filename

                print(f"[{grain}/{metric_label}] Loading {url} ...")
                try:
                    page.goto(url, timeout=30000, wait_until="networkidle")
                    page.wait_for_timeout(5000)

                    # Wait for matrix to render (look for data cells)
                    try:
                        page.wait_for_selector("td[data-matrix-cell-id]", timeout=15000)
                    except:
                        print(f"  WARNING: No matrix cells found for {grain}/{metric_label}")

                    page.screenshot(path=str(filepath), full_page=False)
                    print(f"  Saved: {filepath}")

                    results.append({
                        "grain": grain,
                        "metric": metric_label,
                        "file": filename,
                        "status": "captured",
                    })
                except Exception as e:
                    print(f"  FAILED: {e}")
                    results.append({
                        "grain": grain,
                        "metric": metric_label,
                        "file": filename,
                        "status": "failed",
                        "error": str(e)[:200],
                    })

        browser.close()

    # Write report
    report_path = OUT_DIR.parent / "browser_certification_results.json"
    with open(report_path, "w") as f:
        json.dump({"captured": len([r for r in results if r["status"]=="captured"]),
                    "failed": len([r for r in results if r["status"]!="captured"]),
                    "total": len(results),
                    "results": results}, f, indent=2)

    print(f"\nReport: {report_path}")
    print(f"Captured: {len([r for r in results if r['status']=='captured'])}/{len(results)}")
    return 0 if all(r["status"]=="captured" for r in results) else 1

if __name__ == "__main__":
    sys.exit(capture())
