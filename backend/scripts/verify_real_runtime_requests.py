"""
FASE 3 — Verificación de runtime real.
Ejecuta los 7 requests obligatorios e imprime status, tiempo y muestra de respuesta.
Uso: cd backend && python -m scripts.verify_real_runtime_requests
Requisito: backend corriendo en http://127.0.0.1:8000
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"
TIMEOUT = 120

REQUESTS = [
    ("GET", "/ops/real-lob/drill?period=week&desglose=LOB&segmento=all", "drill week LOB"),
    ("GET", "/ops/real-lob/drill?period=month&desglose=PARK&segmento=all", "drill month PARK"),
    ("GET", "/ops/real-lob/drill/children?country=pe&period=week&period_start=2026-03-09&desglose=LOB&segmento=all", "children week LOB PE"),
    ("GET", "/ops/real-lob/drill/children?country=pe&period=month&period_start=2026-02-01&desglose=PARK&segmento=all", "children month PARK PE"),
    ("GET", "/ops/real-lob/drill/children?country=pe&period=month&period_start=2026-03-01&desglose=SERVICE_TYPE&segmento=all", "children month SERVICE_TYPE PE"),
    ("GET", "/ops/real-margin-quality?days_recent=90&findings_limit=20", "real-margin-quality"),
    ("GET", "/ops/real/margin-quality?days_recent=90&findings_limit=20", "real/margin-quality"),
]


def main():
    print("FASE 3 — Verificación runtime (base=%s, timeout=%ss)" % (BASE, TIMEOUT))
    print("=" * 70)
    for method, path, name in REQUESTS:
        url = BASE + path
        try:
            start = time.perf_counter()
            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read().decode("utf-8", errors="replace")
                elapsed = round((time.perf_counter() - start) * 1000)
            status = r.status
            sample = body[:500] + "..." if len(body) > 500 else body
            try:
                data = json.loads(body)
                if "data" in data and isinstance(data["data"], list) and data["data"]:
                    first = data["data"][0]
                    sample = json.dumps({"data": [first], "_truncated": True}, ensure_ascii=False)[:500]
            except Exception:
                pass
            print("[%s] %s -> %s (%d ms)" % ("OK" if status == 200 else "FAIL", name, status, elapsed))
            print("  Sample: %s" % (sample[:400] + "..." if len(sample) > 400 else sample))
        except urllib.error.HTTPError as e:
            elapsed = 0
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            print("[FAIL] %s -> %s (HTTPError)" % (name, e.code))
            print("  Body: %s" % (body[:300] + "..." if len(body) > 300 else body))
        except Exception as e:
            print("[FAIL] %s -> %s" % (name, type(e).__name__))
            print("  %s" % str(e)[:200])
        print()
    print("=" * 70)
    print("Pegar esta salida en docs/REAL_MODULE_AUDIT_RUNTIME_AND_PERSISTENCE.md FASE 3.")


if __name__ == "__main__":
    main()
