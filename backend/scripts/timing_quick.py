"""Quick timing: measure only the slow individual components."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def t(name, fn):
    t0 = time.perf_counter()
    try:
        result = fn()
        ms = (time.perf_counter() - t0) * 1000
        print(f"  {name}: {ms:.0f}ms")
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        print(f"  {name}: {ms:.0f}ms ERROR: {e}")

from app.services.omniview_v2_source_registry import get_source
src = get_source("CT_TRIPS_2026")
filters = {"country": "peru", "city": "lima"}

print("=== Individual section timings ===")

t("get_source()", lambda: get_source("CT_TRIPS_2026"))

t("get_coverage(CT, day)", lambda: __import__("app.repositories.omniview_v2_source_repository", fromlist=["get_coverage"]).get_coverage("CT_TRIPS_2026", "day"))
t("get_coverage(CT, day, 2026-06-05 to 2026-06-05)", lambda: __import__("app.repositories.omniview_v2_source_repository", fromlist=["get_coverage"]).get_coverage("CT_TRIPS_2026", "day", "2026-06-05", "2026-06-05"))

t("get_freshness(CT, day)", lambda: __import__("app.repositories.omniview_v2_source_repository", fromlist=["get_freshness"]).get_freshness("CT_TRIPS_2026", "day"))

t("get_ct_matrix_data", lambda: __import__("app.repositories.omniview_v2_matrix_repository", fromlist=["get_ct_matrix_data"]).get_ct_matrix_data("day", "2026-06-05", "2026-06-05"))

t("build_source_health", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_source_health"]).build_source_health(src, "day", filters))
t("build_kpi_strip", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_kpi_strip"]).build_kpi_strip(src, "day", "2026-06-05", "2026-06-05", filters))
t("build_operational_coverage", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_operational_coverage"]).build_operational_coverage(src, "day", "2026-06-05", "2026-06-05", filters))
t("build_growth_movement", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_growth_movement"]).build_growth_movement(src, "day", "2026-06-05", "2026-06-05", filters))
t("build_plan_vs_real", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_plan_vs_real_readiness"]).build_plan_vs_real_readiness(src, "2026-06-05", "2026-06-05"))
t("build_slice_readiness", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_slice_readiness"]).build_slice_readiness(src, "2026-06-05", "2026-06-05"))
t("build_lineage", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_lineage_block"]).build_lineage_block(src, "day", filters))
t("build_revenue_integrity", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_revenue_integrity"]).build_revenue_integrity(src, "day", "2026-06-05", "2026-06-05", filters))

print("\n=== Full endpoints ===")
t("build_shell", lambda: __import__("app.services.omniview_v2_shell_service", fromlist=["build_shell"]).build_shell("CT_TRIPS_2026", "day", "2026-06-05", "2026-06-05"))
t("build_matrix", lambda: __import__("app.services.omniview_v2_matrix_view_model_service", fromlist=["build_matrix_response"]).build_matrix_response("CT_TRIPS_2026", "day", "2026-06-05", "2026-06-05"))
