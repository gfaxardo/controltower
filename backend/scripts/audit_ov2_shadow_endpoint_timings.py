"""
OV2-CX.1E — Shadow Endpoint Timing Audit
Measures each OV2 endpoint 10 times, reports p50/p95/max.
"""
import csv, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "omniview_v2_timeout")
os.makedirs(OUTPUT_DIR, exist_ok=True)

from app.services import omniview_v2_source_registry
from app.services.omniview_v2_core_service import get_omniview_v2_summary
from app.services.omniview_v2_shell_service import build_shell
from app.services.omniview_v2_matrix_view_model_service import build_matrix_response
from app.repositories.omniview_v2_matrix_repository import get_ct_matrix_data, get_yango_matrix_data
from app.repositories.omniview_v2_source_repository import get_coverage, get_freshness

ITERATIONS = 5
SOURCES_FN = lambda: ([omniview_v2_source_registry.get_supported_sources()], None, 0)
SHELL_0605_FN = lambda: (build_shell("CT_TRIPS_2026", "day", "2026-06-05", "2026-06-05", {"country":"peru","city":"lima"}), None, 0)
MATRIX_0605_FN = lambda: (build_matrix_response("CT_TRIPS_2026", "day", "2026-06-05", "2026-06-05", {"country":"peru","city":"lima"}), None, 0)
SHELL_0606_FN = lambda: (build_shell("CT_TRIPS_2026", "day", "2026-06-06", "2026-06-06", {"country":"peru","city":"lima"}), None, 0)
MATRIX_0606_FN = lambda: (build_matrix_response("CT_TRIPS_2026", "day", "2026-06-06", "2026-06-06", {"country":"peru","city":"lima"}), None, 0)

# Section-level timing: shell service internals
def time_shell_sections():
    from app.services.omniview_v2_source_registry import get_source
    src = get_source("CT_TRIPS_2026")
    filters = {"country": "peru", "city": "lima"}

    timings = {}

    t0 = time.perf_counter()
    from app.services.omniview_v2_shell_service import build_source_health
    build_source_health(src, "day", filters)
    timings["source_health_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    from app.services.omniview_v2_shell_service import build_kpi_strip
    build_kpi_strip(src, "day", "2026-06-05", "2026-06-05", filters)
    timings["kpi_strip_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    from app.services.omniview_v2_shell_service import build_operational_coverage
    build_operational_coverage(src, "day", "2026-06-05", "2026-06-05", filters)
    timings["operational_coverage_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    from app.services.omniview_v2_shell_service import build_growth_movement
    build_growth_movement(src, "day", "2026-06-05", "2026-06-05", filters)
    timings["growth_movement_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    from app.services.omniview_v2_shell_service import build_plan_vs_real_readiness
    build_plan_vs_real_readiness(src, "2026-06-05", "2026-06-05")
    timings["plan_vs_real_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    from app.services.omniview_v2_shell_service import build_slice_readiness
    build_slice_readiness(src, "2026-06-05", "2026-06-05")
    timings["slice_readiness_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    from app.services.omniview_v2_shell_service import build_lineage_block
    build_lineage_block(src, "day", filters)
    timings["lineage_ms"] = round((time.perf_counter() - t0) * 1000)

    return timings


def measure(label, fn):
    times = []
    sizes = []
    for i in range(ITERATIONS):
        t0 = time.perf_counter()
        result, _, _ = fn()
        elapsed = time.perf_counter() - t0
        times.append(elapsed * 1000)
        if result is not None:
            try:
                sizes.append(len(json.dumps(result.to_dict() if hasattr(result, 'to_dict') else result, default=str)))
            except:
                sizes.append(0)
        else:
            sizes.append(0)

    times.sort()
    p50 = times[len(times)//2]
    p95 = times[int(len(times)*0.95)] if len(times) > 1 else times[-1]
    max_t = max(times)
    avg_size = sum(sizes)//len(sizes) if sizes else 0

    return {
        "endpoint": label, "iterations": ITERATIONS,
        "p50_ms": p50, "p95_ms": p95, "max_ms": max_t,
        "avg_size_bytes": avg_size, "timeout_count": sum(1 for t in times if t > 15000),
    }


ENDPOINTS = [
    ("sources", SOURCES_FN),
    ("shell_0605", SHELL_0605_FN),
    ("matrix_0605", MATRIX_0605_FN),
    ("shell_0606", SHELL_0606_FN),
    ("matrix_0606", MATRIX_0606_FN),
]

print("=" * 60)
print("OV2-CX.1E Endpoint Timing Audit")
print("=" * 60)

results = []
for name, fn in ENDPOINTS:
    print(f"\n[{name}] {ITERATIONS} iterations...")
    r = measure(name, fn)
    results.append(r)
    status = "TIMEOUT" if r["timeout_count"] > 0 else "OK"
    print(f"  p50={r['p50_ms']:.0f}ms p95={r['p95_ms']:.0f}ms max={r['max_ms']:.0f}ms size={r['avg_size_bytes']}B {status}")

print("\n--- Section-level timings ---")
section_times = time_shell_sections()
for k, v in sorted(section_times.items(), key=lambda x: -x[1]):
    cls = "CRITICAL" if v > 10000 else "SLOW" if v > 3000 else "OK" if v < 1500 else "FAST" if v < 500 else "OK"
    print(f"  {k}: {v}ms [{cls}]")

# CSV
csv_path = os.path.join(OUTPUT_DIR, "endpoint_timings.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader()
    w.writerows(results)

# Markdown summary
md = [
    "# OV2-CX.1E Endpoint Timing Summary",
    "",
    "| Endpoint | p50 | p95 | Max | Size | Timeouts |",
    "|----------|-----|-----|-----|------|----------|",
]
for r in results:
    md.append(f"| {r['endpoint']} | {r['p50_ms']:.0f}ms | {r['p95_ms']:.0f}ms | {r['max_ms']:.0f}ms | {r['avg_size_bytes']}B | {r['timeout_count']} |")

md += ["", "## Section Timings", "", "| Section | Time | Class |", "|---------|------|-------|"]
for k, v in sorted(section_times.items(), key=lambda x: -x[1]):
    cls = "CRITICAL" if v > 10000 else "SLOW" if v > 3000 else "OK"
    md.append(f"| {k} | {v}ms | {cls} |")

summary_path = os.path.join(OUTPUT_DIR, "endpoint_timings_summary.md")
with open(summary_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print(f"\n[output] {OUTPUT_DIR}")
print("Done.")
