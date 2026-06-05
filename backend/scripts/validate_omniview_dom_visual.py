"""O4.1 — Automated F1-F10 DOM validation via Playwright."""
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
GRAINS = ["daily", "weekly", "monthly"]
METRIC_KEYS = ["trips_completed", "revenue_yego_net", "active_drivers", "avg_ticket", "trips_per_driver"]

def validate():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        for grain in GRAINS:
            for mkey in METRIC_KEYS:
                url = f"{BASE_URL}/?tab=omniview&grain={grain}&kpi={mkey}"
                label = f"{grain}/{mkey}"
                print(f"[{label}] Validating...")

                try:
                    page.goto(url, timeout=30000, wait_until="networkidle")
                    page.wait_for_timeout(4000)
                except Exception as e:
                    results.append({"label": label, "F1": "ERROR", "detail": str(e)[:100]})
                    continue

                body = page.content()

                # F1: Forbidden tokens
                forbidden = {
                    "[object Object]": body.count("[object Object]"),
                    "NaN": body.count(">NaN<") + body.count(" NaN ") + body.count("NaN%"),
                    "undefined": body.count(">undefined<"),
                    "null": body.count(">null<"),
                    "Infinity": body.count("Infinity"),
                }
                f1_pass = all(v == 0 for v in forbidden.values())

                # F3: Current period visible - check for blue ring or badge
                has_badge = "HOY" in body or "SEMANA ACTUAL" in body or "MES ACTUAL" in body
                has_ring = "ring-blue-400" in body

                # F8: Confidence numeric - check for "Confianza" with number
                import re
                conf_match = re.search(r'Confianza\s+(\d+)%', body)
                has_confidence = conf_match is not None
                conf_value = int(conf_match.group(1)) if conf_match else None

                # F10: Freshness coherence - check no "Falta data" when matrix has data
                has_falta = "Falta data" in body
                has_matrix_cells = "data-matrix-cell-id" in body
                f10_coherent = not (has_falta and has_matrix_cells)

                fails = []
                if not f1_pass:
                    fails.append(f"F1: {json.dumps(forbidden)}")
                if not has_badge and not has_ring:
                    fails.append("F3: current period not identifiable")
                if not has_confidence:
                    fails.append("F8: confidence not numeric or not found")
                if not f10_coherent:
                    fails.append("F10: freshness contradicts data")

                status = "PASS" if not fails else "FAIL"
                results.append({
                    "label": label,
                    "status": status,
                    "F1_pass": f1_pass,
                    "F3_identifiable": has_badge or has_ring,
                    "F8_confidence": conf_value,
                    "F10_coherent": f10_coherent,
                    "fails": fails,
                })

        browser.close()

    passed = len([r for r in results if r["status"] == "PASS"])
    failed = len([r for r in results if r["status"] != "PASS"])
    print(f"\n{'='*60}")
    print(f"  DOM VALIDATION: {passed} PASS, {failed} FAIL / {len(results)} total")
    for r in results:
        tag = "PASS" if r["status"]=="PASS" else "FAIL"
        print(f"  [{tag}] {r['label']} F1={r['F1_pass']} F3={r['F3_identifiable']} F8={r['F8_confidence']} F10={r['F10_coherent']}")
        if r["fails"]:
            for f in r["fails"]:
                print(f"         {f}")
    print()

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(validate())
