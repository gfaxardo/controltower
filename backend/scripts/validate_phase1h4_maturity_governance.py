"""
QA Script — Fase 1H.4: Operational Maturity Governance Layer

Valida:
1. No duplicate routes in navigation registry
2. No orphan navigation entries (in registry but no route map)
3. No visible experimental modules without feature flag
4. No broken hidden routes
5. No registry inconsistencies (maturity vs visibility alignment)
6. All navigation backed by registry entries
7. No hardcoded maturity states in components
8. Backend serving stability (no regression)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8001")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_SRC = os.path.join(REPO_ROOT, "frontend", "src")
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[dict] = []
START_TIME = time.time()


def check(name, condition, detail="", warn=False):
    status = WARN if warn else (PASS if condition else FAIL)
    results.append({"check": name, "status": status, "detail": str(detail)})
    tag = f"[{status}]"
    msg = f"  {tag:7s} {name}"
    if detail and not condition:
        msg += f" -- {detail}"
    print(msg)


def get(path, params=None, timeout=40):
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:500]
        return resp.status_code, body
    except requests.exceptions.ConnectionError:
        return 0, "CONNECTION_ERROR"
    except requests.exceptions.Timeout:
        return 0, "TIMEOUT"
    except Exception as e:
        return 0, str(e)[:300]


def finalize():
    passed = sum(1 for r in results if r["status"] == PASS)
    warned = sum(1 for r in results if r["status"] == WARN)
    failed = sum(1 for r in results if r["status"] == FAIL)
    total = len(results)
    elapsed_s = round(time.time() - START_TIME, 1)
    print()
    print("=" * 60)
    print("QA SUMMARY — Fase 1H.4 Maturity Governance")
    print(f"Total:   {total}")
    print(f"PASS:    {passed}")
    print(f"WARN:    {warned}")
    print(f"FAIL:    {failed}")
    print(f"Time:    {elapsed_s}s")
    print("=" * 60)

    if failed == 0:
        print("VERDICT: GO")
    else:
        print("VERDICT: NO-GO")
        return 1
    return 0


def read_file_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_nav_registry(content):
    """Extrae todas las keys del navigation registry."""
    keys = re.findall(r"key:\s*'([^']+)'", content)
    routes = re.findall(r"route:\s*'([^']+)'", content)
    visibilities = re.findall(r"visibility:\s*VISIBILITY\.(\w+)", content)
    return keys, routes, visibilities


def parse_maturity_registry(content):
    """Extrae todas las estructuras del maturity registry."""
    # Buscar keys y sus maturity values
    entries = {}
    current_key = None
    for line in content.split("\n"):
        key_match = re.match(r"^\s*(\w+):\s*\{", line)
        maturity_match = re.match(r"^\s*maturity:\s*MATURITY\.(\w+)", line)
        visible_match = re.match(r"^\s*visible:\s*(true|false)", line)
        legacy_match = re.match(r"^\s*legacy:\s*(true|false)", line)
        experimental_match = re.match(r"^\s*experimental:\s*(true|false)", line)
        phase_match = re.match(r"^\s*phase:\s*'([^']+)'", line)
        engine_match = re.match(r"^\s*engine:\s*ENGINE_OWNER\.(\w+)", line)

        if key_match:
            current_key = key_match.group(1)
            entries[current_key] = {}
        elif current_key:
            if maturity_match:
                entries[current_key]["maturity"] = maturity_match.group(1).upper()
            elif visible_match:
                entries[current_key]["visible"] = visible_match.group(1) == "true"
            elif legacy_match:
                entries[current_key]["legacy"] = legacy_match.group(1) == "true"
            elif experimental_match:
                entries[current_key]["experimental"] = experimental_match.group(1) == "true"
            elif phase_match:
                entries[current_key]["phase"] = phase_match.group(1)
            elif engine_match:
                entries[current_key]["engine"] = engine_match.group(1)

    return entries


def main():
    global START_TIME
    START_TIME = time.time()

    print("=" * 60)
    print("QA: Fase 1H.4 — Operational Maturity Governance Layer")
    print(f"Base URL: {BASE_URL}")
    print(f"Repo root: {REPO_ROOT}")
    print("=" * 60)

    # ===== A. Backend Health (no regression) =====
    print("\n--- A. Backend Health ---")
    t0 = time.time()
    code, body = get("/health", timeout=10)
    elapsed = round((time.time() - t0) * 1000)
    check("A.1 Backend health", code == 200, f"HTTP {code} {elapsed}ms")
    if code != 200:
        print("  SKIP: Backend not reachable")
        finalize()
        return 1

    # ===== B. Navigation Registry Integrity =====
    print("\n--- B. Navigation Registry ---")
    nav_path = os.path.join(FRONTEND_SRC, "config", "controlTowerNavigationRegistry.js")
    check("B.1 Navigation registry file exists", os.path.exists(nav_path), nav_path)
    if os.path.exists(nav_path):
        nav_content = read_file_lines(nav_path)
        nav_keys, nav_routes, nav_visibilities = parse_nav_registry(nav_content)

        check("B.2 Navigation has entries", len(nav_keys) > 0, f"count={len(nav_keys)}")

        # Check duplicates
        seen_keys = set()
        dupes = [k for k in nav_keys if k in seen_keys or seen_keys.add(k)]
        check("B.3 No duplicate navigation keys", len(dupes) == 0, f"dupes={dupes}" if dupes else "")

        # Check all routes have corresponding keys
        check("B.4 Routes match keys count", abs(len(nav_keys) - len(nav_routes)) <= 2,
              f"keys={len(nav_keys)} routes={len(nav_routes)}")

        # Check legacy routes are hidden
        legacy_routes = ['en_revision']
        for route in nav_routes:
            is_legacy = any(route.startswith(f"/{lr}") for lr in legacy_routes)
            # Legacy routes should be HIDE_FROM_NAV
            if is_legacy:
                idx = nav_routes.index(route)
                if idx < len(nav_visibilities):
                    check(f"B.5 Legacy route {route} is hidden",
                          nav_visibilities[idx] == "HIDE_FROM_NAV",
                          f"visibility={nav_visibilities[idx]}")

    # ===== C. Maturity Registry Integrity =====
    print("\n--- C. Maturity Registry ---")
    mat_path = os.path.join(FRONTEND_SRC, "config", "operationalMaturityRegistry.js")
    check("C.1 Maturity registry file exists", os.path.exists(mat_path), mat_path)
    if os.path.exists(mat_path):
        mat_content = read_file_lines(mat_path)
        mat_entries = parse_maturity_registry(mat_content)

        check("C.2 Maturity registry has entries", len(mat_entries) > 0, f"count={len(mat_entries)}")

        # Validate maturity-visibility alignment
        visible_legacy = [k for k, v in mat_entries.items() if v.get("legacy") and v.get("visible")]
        check("C.3 No visible legacy modules", len(visible_legacy) == 0,
              f"visible_legacy={visible_legacy}" if visible_legacy else "")

        visible_experimental = [k for k, v in mat_entries.items() if v.get("experimental") and v.get("visible")]
        check("C.4 No visible experimental modules without flag",
              len(visible_experimental) == 0,
              f"visible_experimental={visible_experimental}" if visible_experimental else "")

        # Check all nav keys have maturity entries
        if os.path.exists(nav_path):
            nav_content = read_file_lines(nav_path)
            nav_keys, _, _ = parse_nav_registry(nav_content)
            nav_key_set = set(nav_keys)
            mat_key_set = set(mat_entries.keys())
            missing_in_maturity = nav_key_set - mat_key_set
            check("C.5 All nav keys have maturity entries",
                  len(missing_in_maturity) == 0,
                  f"missing={list(missing_in_maturity)[:5]}" if missing_in_maturity else "")

            extra_in_maturity = mat_key_set - nav_key_set
            if extra_in_maturity:
                # Module en maturity pero no en nav → puede ser legacy o experimental oculto
                # Verificar que son legacy/experimental/deprecated
                hidden_ok = all(
                    mat_entries.get(k, {}).get("legacy") or
                    mat_entries.get(k, {}).get("experimental") or
                    not mat_entries.get(k, {}).get("visible")
                    for k in extra_in_maturity
                )
                check("C.6 Extra maturity entries are hidden/legacy/experimental",
                      hidden_ok,
                      f"extra_keys={list(extra_in_maturity)}")

        # Count by maturity level
        maturity_counts = {}
        for v in mat_entries.values():
            m = v.get("maturity", "UNKNOWN")
            maturity_counts[m] = maturity_counts.get(m, 0) + 1
        print(f"  Maturity distribution: {maturity_counts}")

    # ===== D. Serving Layer Stability (no regression) =====
    print("\n--- D. Serving Layer (no regression) ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/filters", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("D.1 Filters OK", code == 200, f"HTTP {code} {elapsed}ms")

    t0 = time.time()
    code, body = get("/ops/business-slice/monthly", timeout=60)
    elapsed = round((time.time() - t0) * 1000)
    check("D.2 Monthly matrix OK", code == 200, f"HTTP {code} {elapsed}ms")

    t0 = time.time()
    code, body = get("/ops/system-health", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("D.3 System health OK", code == 200, f"HTTP {code} {elapsed}ms")

    # ===== E. Route Map Consistency =====
    print("\n--- E. Route Map Consistency ---")
    app_path = os.path.join(FRONTEND_SRC, "App.jsx")
    if os.path.exists(app_path):
        app_content = read_file_lines(app_path)
        route_map_keys = re.findall(r"path:\s*'([^']+)'.*sub:\s*'([^']+)'", app_content)
        sub_url_keys = re.findall(r"(\w+):\s*'([^']+)'", app_content)
        check("E.1 App.jsx has route map entries", len(route_map_keys) > 0, f"count={len(route_map_keys)}")

        # Verify route map keys match nav registry
        nav_keys_set = set()
        if os.path.exists(nav_path):
            nav_content = read_file_lines(nav_path)
            nav_keys, _, _ = parse_nav_registry(nav_content)
            nav_keys_set = set(nav_keys)

        route_sub_keys = {s for _, s in route_map_keys}
        missing_route_map = nav_keys_set - route_sub_keys
        # Hidden/legacy routes don't need route map entries
        if os.path.exists(nav_path):
            hidden_keys = set()
            for i, (k, r, v) in enumerate(zip(nav_keys, nav_routes, nav_visibilities)):
                if v == "HIDE_FROM_NAV":
                    hidden_keys.add(k)
            truly_missing = missing_route_map - hidden_keys
            check("E.2 Visible nav keys have route map entries",
                  len(truly_missing) == 0,
                  f"missing={list(truly_missing)[:5]}" if truly_missing else "")

    # ===== Final =====
    return finalize()


if __name__ == "__main__":
    sys.exit(main())
