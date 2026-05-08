"""
P2 — Auditoría KPI multi-grain Omniview (facts ops.real_business_slice_*_fact).

Orquesta escenarios (país/ciudad/slice) y periodos derivados de MAX(trip_date) en day_fact.
Reutiliza la lógica canónica de `validate_kpi_grain_consistency.run_consistency_audit`
(daily_in_month vs monthly; weekly ISO full solo informativo).

Uso (desde backend/):
  python -m scripts.audit_kpi_consistency_multigrain
  python -m scripts.audit_kpi_consistency_multigrain --year 2026 --month 4 --no-auto-periods
  python -m scripts.audit_kpi_consistency_multigrain --scenarios pe:lima,co:cali
  python -m scripts.audit_kpi_consistency_multigrain --p2b

Salida:
  backend/scripts/outputs/kpi_multigrain_audit_<ts>.json
  docs/PHASE1_KPI_CONSISTENCY_AUDIT.md (resumen ejecutivo)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.db.connection import get_db, init_db_pool  # noqa: E402
from psycopg2.extras import RealDictCursor  # noqa: E402
from app.utils.kpi_multigrain_audit import (  # noqa: E402
    diff_pct,
    map_validation_status_to_audit,
)
from scripts.validate_kpi_grain_consistency import (  # noqa: E402
    run_consistency_audit,
    summarize,
)


@dataclass
class Scenario:
    country: Optional[str]
    city: Optional[str]
    business_slice: Optional[str]
    label: str


DEFAULT_SCENARIOS: List[Scenario] = [
    Scenario("pe", "lima", None, "PE_Lima"),
    Scenario("pe", "trujillo", None, "PE_Trujillo"),
    Scenario(None, None, None, "GLOBAL"),
    Scenario("co", None, None, "CO_country"),
    Scenario("pe", None, None, "PE_country"),
]


def _last_closed_calendar_month(ref: date) -> Tuple[int, int]:
    first_current = ref.replace(day=1)
    last_prev = first_current - timedelta(days=1)
    return last_prev.year, last_prev.month


def _reference_trip_date(cur) -> Optional[date]:
    cur.execute("SELECT MAX(trip_date)::date AS mx FROM ops.real_business_slice_day_fact")
    row = cur.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return row.get("mx")
    return row[0]


def _row_to_checks(
    raw_rows: List[Dict[str, Any]],
    scenario: Scenario,
    period_label: str,
    y: int,
    m: int,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in raw_rows:
        exp = float(r.get("monthly_value") or 0)
        act = float(r.get("daily_sum_in_month") or 0)
        d_abs = abs(exp - act)
        d_pc = diff_pct(exp, act)
        st = map_validation_status_to_audit(str(r.get("status") or ""))
        out.append(
            {
                "check_name": f"omniview_{r.get('kpi')}_monthly_vs_daily_in_month",
                "grain": "monthly<=daily_sum",
                "country": r.get("country") or scenario.country or "",
                "city": r.get("city") or scenario.city or "",
                "lob": r.get("business_slice") or "",
                "period": period_label,
                "calendar_month": f"{y}-{m:02d}",
                "expected_value": exp,
                "actual_value": act,
                "diff_abs": d_abs,
                "diff_pct": None if d_pc is None or (math.isnan(d_pc) if isinstance(d_pc, float) else False) else round(d_pc, 4),
                "status": st,
                "explanation": (r.get("issue_note") or r.get("status") or "").strip(),
                "source_expected": "ops.real_business_slice_month_fact",
                "source_actual": "SUM(ops.real_business_slice_day_fact en mes calendario)",
                "validation_basis": r.get("validation_basis"),
                "weekly_sum_full_iso_informative": float(r.get("weekly_sum_full_iso") or 0),
            }
        )
    return out


def _parse_scenarios(spec: Optional[str]) -> List[Scenario]:
    if not spec:
        return list(DEFAULT_SCENARIOS)
    out: List[Scenario] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        label = part
        country = city = bs = None
        if ":" in part:
            segs = part.split(":")
            if len(segs) >= 3:
                country = segs[0].strip() or None
                city = segs[1].strip() or None
                bs = ":".join(segs[2:]).strip() or None
            elif len(segs) == 2:
                country = segs[0].strip() or None
                city = segs[1].strip() or None
        else:
            country = part or None
        out.append(Scenario(country, city, bs, label))
    return out or list(DEFAULT_SCENARIOS)


def _write_phase1_doc(
    path: Path,
    all_checks: List[Dict[str, Any]],
    summary_counts: Dict[str, int],
    ref_date: Optional[date],
    periods_run: List[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fails = [c for c in all_checks if c.get("status") == "fail"]
    warns = [c for c in all_checks if c.get("status") == "warning"]
    nc = [c for c in all_checks if c.get("status") == "not_certified"]

    if not all_checks:
        verdict = (
            "P2 KPI CONSISTENCY NO CERTIFICADO — 0 checks (sin celdas merged>0 para filtros/periodo; "
            "ver diagnostics: alias país/ciudad vs facts, o periodo sin datos)"
        )
    elif fails:
        verdict = "P2 KPI CONSISTENCY NO-GO"
    elif warns:
        verdict = "P2 KPI CONSISTENCY GO (condicionado: revisar warnings)"
    else:
        verdict = "P2 KPI CONSISTENCY GO"


    lines = [
        "# FASE 1 — P2 KPI consistency (auto-generado)",
        "",
        "## Resumen ejecutivo",
        "",
        f"- **Fecha referencia (MAX day_fact.trip_date):** {ref_date}",
        f"- **Periodos evaluados:** {', '.join(periods_run)}",
        f"- **Checks totales:** {len(all_checks)} (si 0, no hay celdas en month/week/day facts para los filtros)",
        f"- **ok / warning / fail / not_certified (agregado validator):** {summary_counts}",
        f"- **Veredicto:** **{verdict}**",
        "",
        "## Fuentes por grain (Omniview Matrix REAL)",
        "",
        "| Grain | Tabla | Columna tiempo | KPIs (extracto) |",
        "|-------|-------|------------------|-------------------|",
        "| Daily | `ops.real_business_slice_day_fact` | `trip_date` | `trips_completed`, `trips_cancelled`, `active_drivers`, `revenue_yego_net`, componentes ticket |",
        "| Weekly | `ops.real_business_slice_week_fact` | `week_start` (ISO) | mismas columnas agregadas |",
        "| Monthly | `ops.real_business_slice_month_fact` | `month` (primer día mes) | mismas columnas |",
        "",
        "- **Completados vs cancelados:** `trips_completed` y `trips_cancelled` son columnas separadas; KPIs de volumen completado usan `trips_completed`.",
        "- **active_drivers:** semi-aditivo (distinct por periodo en agregación); no comparar con SUM(daily).",
        "- **avg_ticket:** derivado de `ticket_sum_completed` / `ticket_count_completed` (no promedio de promedios).",
        "",
        "## Normalización de filtros (CLI vs columnas en facts)",
        "",
        "- País: alias `pe`→`peru`, `co`→`colombia`; comparación con `lower(trim(country))`.",
        "- Ciudad / business_slice: comparación case-insensitive en SQL.",
        "- No se alteran datos en tablas; solo cómo el validador empareja el filtro.",
        "",
        "## Regla canónica multi-grain (aditivos)",
        "",
        "Para KPIs aditivos, la base de FAIL es **monthly_value ≈ SUM(day_fact en mes calendario)**.",
        "La suma de **semanas ISO completas** que tocan el mes (`weekly_sum_full_iso`) es **solo informativa**",
        "(cruce semana/mes documentado en `validate_kpi_grain_consistency.py`).",
        "",
        "## Resultados",
        "",
        f"- **FAIL:** {len(fails)}",
        f"- **WARNING:** {len(warns)}",
        f"- **not_certified:** {len(nc)}",
        "",
        "### Bloqueadores (status=fail)",
        "",
    ]
    if not fails:
        lines.append("_Ninguno._")
    else:
        for c in fails[:50]:
            lines.append(
                f"- `{c.get('check_name')}` | {c.get('country')}/{c.get('city')}/{c.get('lob')} | "
                f"{c.get('period')} | diff_abs={c.get('diff_abs')}"
            )
        if len(fails) > 50:
            lines.append(f"- … y {len(fails) - 50} más (ver JSON).")

    lines.extend(
        [
            "",
            "## Riesgos remanentes",
            "",
            "- Ventana **mes abierto**: datos parciales pueden generar warning entre daily y monthly.",
            "- **Cross-country revenue:** no se mezclan monedas en un solo total; filtros por país.",
            "",
            "## Artefacto JSON",
            "",
            "Ver `backend/scripts/outputs/kpi_multigrain_audit_*.json` para detalle reproducible.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")

def fetch_auto_scenarios_from_db(cur, year: int, month: int) -> List[Scenario]:
    """
    Escenarios derivados de ops.real_business_slice_month_fact para un mes calendario.
    Valores de dimensión según BD (p. ej. peru, colombia); sin asumir 'pe'/'Lima' como literales.
    """
    m0 = date(year, month, 1)
    out: List[Scenario] = []

    cur.execute(
        """
        SELECT country, SUM(trips_completed)::bigint AS t
        FROM ops.real_business_slice_month_fact
        WHERE month = %s::date
        GROUP BY 1
        ORDER BY t DESC NULLS LAST
        LIMIT 1
        """,
        (m0,),
    )
    row = cur.fetchone()
    if row and row[0]:
        out.append(Scenario(row[0], None, None, f"top_country:{row[0]}"))

    cur.execute(
        """
        SELECT country, city, SUM(trips_completed)::bigint AS t
        FROM ops.real_business_slice_month_fact
        WHERE month = %s::date
        GROUP BY 1, 2
        ORDER BY t DESC NULLS LAST
        LIMIT 1
        """,
        (m0,),
    )
    row = cur.fetchone()
    if row and row[0]:
        out.append(Scenario(row[0], row[1], None, f"top_country_city:{row[0]}:{row[1]}"))

    cur.execute(
        """
        SELECT business_slice_name, SUM(trips_completed)::bigint AS t
        FROM ops.real_business_slice_month_fact
        WHERE month = %s::date
        GROUP BY 1
        ORDER BY t DESC NULLS LAST
        LIMIT 1
        """,
        (m0,),
    )
    row = cur.fetchone()
    if row and row[0]:
        out.append(Scenario(None, None, row[0], f"top_business_slice:{row[0]}"))

    for country, city, lab in [
        ("peru", "lima", "anchor_peru_lima"),
        ("colombia", "cali", "anchor_co_cali"),
        ("peru", "trujillo", "anchor_peru_trujillo"),
        ("colombia", "medellin", "anchor_co_medellin"),
        ("peru", "arequipa", "anchor_peru_arequipa"),
    ]:
        cur.execute(
            """
            SELECT 1 FROM ops.real_business_slice_month_fact
            WHERE month = %s::date
              AND lower(trim(country::text)) = %s
              AND lower(trim(city::text)) = %s
            LIMIT 1
            """,
            (m0, country, city),
        )
        if cur.fetchone():
            out.append(Scenario(country, city, None, lab))

    for country, lab in [("colombia", "anchor_colombia"), ("peru", "anchor_peru")]:
        cur.execute(
            """
            SELECT 1 FROM ops.real_business_slice_month_fact
            WHERE month = %s::date AND lower(trim(country::text)) = %s
            LIMIT 1
            """,
            (m0, country),
        )
        if cur.fetchone():
            out.append(Scenario(country, None, None, lab))

    for sl, lab in [("Delivery", "anchor_slice_Delivery"), ("Auto regular", "anchor_slice_Auto_regular")]:
        cur.execute(
            """
            SELECT 1 FROM ops.real_business_slice_month_fact
            WHERE month = %s::date
              AND lower(trim(business_slice_name::text)) = lower(trim(%s))
            LIMIT 1
            """,
            (m0, sl),
        )
        if cur.fetchone():
            out.append(Scenario(None, None, sl, lab))

    out.append(Scenario(None, None, None, "GLOBAL"))
    return _dedupe_scenarios(out)


def _dedupe_scenarios(scenarios: List[Scenario]) -> List[Scenario]:
    seen = set()
    out: List[Scenario] = []
    for s in scenarios:
        k = (s.country, s.city, s.business_slice)
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _window_meta_from_db(cur, ref: date) -> Dict[str, Any]:
    """Cobertura informativa: ventanas cortas vs grano mensual canónico."""
    d14 = ref - timedelta(days=13)
    cur.execute(
        """
        SELECT
          COALESCE(SUM(trips_completed), 0)::float,
          COALESCE(SUM(revenue_yego_net), 0)::float
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= %s::date AND trip_date <= %s::date
        """,
        (d14, ref),
    )
    t14, r14 = cur.fetchone()
    cur.execute(
        """
        SELECT date_trunc('week', trip_date)::date AS ws,
               SUM(trips_completed)::float AS tr
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= %s::date AND trip_date <= %s::date
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT 4
        """,
        (ref - timedelta(days=27), ref),
    )
    last4w = [{"week_start": r[0].isoformat() if r[0] else None, "trips_completed": r[1]} for r in cur.fetchall()]
    return {
        "note": (
            "Validación contractual P2 sigue siendo mensual (daily_in_month vs monthly). "
            "Ventanas 14d/4w son contexto cuantitativo, no un segundo criterio de FAIL."
        ),
        "last_14d_from_max_trip_date": {
            "trip_date_from": d14.isoformat(),
            "trip_date_to": ref.isoformat(),
            "sum_trips_completed_daily_fact": t14,
            "sum_revenue_yego_net_daily_fact": r14,
        },
        "last_4_iso_week_buckets_in_28d_lookback": last4w,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P2 audit KPI multi-grain Omniview")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--month", type=int, default=None)
    parser.add_argument(
        "--no-auto-periods",
        action="store_true",
        help="Usar solo --year/--month explícitos (no derivar de MAX(trip_date))",
    )
    parser.add_argument("--also-current-month", action="store_true", help="Auditar también el mes calendario de ref_date")
    parser.add_argument(
        "--p2b",
        action="store_true",
        help="P2B: periodos last_closed + mes actual (si hay días) y escenarios descubiertos en facts (sin hardcode de slice/ciudad)",
    )
    parser.add_argument("--scenarios", type=str, default=None, help="Ej: pe:lima,pe:trujillo,co:cali,peru:lima:Delivery")
    parser.add_argument("--doc", type=str, default=None, help="Ruta markdown salida")
    args = parser.parse_args()

    if args.p2b and (args.year or args.month or args.no_auto_periods):
        print("[audit] --p2b no debe combinarse con --year/--month/--no-auto-periods; se ignorará lo manual.", flush=True)

    init_db_pool()

    ref_date: Optional[date] = None
    window_meta: Optional[Dict[str, Any]] = None
    scenarios_from_db: Optional[List[Scenario]] = None

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        ref_date = _reference_trip_date(cur)
        cur.close()

    periods: List[Tuple[int, int, str]] = []
    if args.p2b:
        if not ref_date:
            print("[audit] P2B requiere MAX(trip_date) en day_fact.", flush=True)
            return 2
        yl, ml = _last_closed_calendar_month(ref_date)
        periods.append((yl, ml, "last_closed_month"))
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*)::bigint FROM ops.real_business_slice_day_fact
                WHERE trip_date >= %s::date
                """,
                (date(ref_date.year, ref_date.month, 1),),
            )
            n_open = cur.fetchone()[0]
            if n_open > 0:
                periods.append((ref_date.year, ref_date.month, "current_calendar_month_open"))
            scenarios_from_db = fetch_auto_scenarios_from_db(cur, yl, ml)
            window_meta = _window_meta_from_db(cur, ref_date)
            cur.close()
    elif args.year and args.month:
        periods.append((args.year, args.month, "manual"))
    elif not args.no_auto_periods and ref_date:
        yc, mc = ref_date.year, ref_date.month
        yl, ml = _last_closed_calendar_month(ref_date)
        periods.append((yl, ml, "last_closed_month"))
        if args.also_current_month:
            periods.append((yc, mc, "current_calendar_month_open"))
    else:
        print("[audit] Sin periodos: pase --year/--month o asegure day_fact poblada.", flush=True)
        return 2

    if scenarios_from_db is not None:
        scenarios = scenarios_from_db
    else:
        scenarios = _parse_scenarios(args.scenarios)

    print(
        f"[audit] Escenarios ({len(scenarios)}): " + ", ".join(s.label for s in scenarios),
        flush=True,
    )

    all_checks: List[Dict[str, Any]] = []
    agg_summary: Dict[str, int] = {"ok": 0, "expected_non_comparable": 0, "warning": 0, "fail": 0, "not_certified": 0}

    for y, m, plab in periods:
        for sc in scenarios:
            raw = run_consistency_audit(
                y, m, sc.country, sc.city, sc.business_slice
            )
            counts = summarize(raw)
            for k, v in counts.items():
                agg_summary[k] = agg_summary.get(k, 0) + v
            for r in raw:
                r["scenario_label"] = sc.label
                r["period_run"] = plab
            all_checks.extend(
                _row_to_checks(
                    raw,
                    sc,
                    f"{plab}_{sc.label}",
                    y,
                    m,
                )
            )

    if ref_date and window_meta is None:
        with get_db() as conn:
            cur = conn.cursor()
            window_meta = _window_meta_from_db(cur, ref_date)
            cur.close()

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_json = _HERE / "outputs" / f"kpi_multigrain_audit_{ts}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "reference_trip_date": ref_date.isoformat() if ref_date else None,
        "periods": [{"y": a, "m": b, "label": c} for a, b, c in periods],
        "scenarios": [
            {
                "label": s.label,
                "country": s.country,
                "city": s.city,
                "business_slice": s.business_slice,
            }
            for s in scenarios
        ],
        "checks": all_checks,
        "raw_summary_counts": agg_summary,
    }
    if window_meta is not None:
        payload["short_window_context_from_daily_fact"] = window_meta
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(
            payload,
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[audit] JSON: {out_json}", flush=True)

    doc_path = Path(args.doc) if args.doc else (_BACKEND.parent / "docs" / "PHASE1_KPI_CONSISTENCY_AUDIT.md")
    map_st = {
        "ok": agg_summary.get("ok", 0),
        "warning": agg_summary.get("warning", 0),
        "fail": agg_summary.get("fail", 0),
        "not_certified": agg_summary.get("expected_non_comparable", 0) + agg_summary.get("not_certified", 0),
    }
    _write_phase1_doc(
        doc_path,
        all_checks,
        map_st,
        ref_date,
        [f"{a}-{b:02d}({c})" for a, b, c in periods],
    )
    print(f"[audit] Doc: {doc_path}", flush=True)

    if agg_summary.get("fail", 0) > 0:
        return 2
    if agg_summary.get("warning", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
