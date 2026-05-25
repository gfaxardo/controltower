"""
Momentum Drill Service — Omniview momentum series serving fact.

Proporciona series históricas comparables:
- Daily: same-weekday series (N últimos domingos, lunes, etc.)
- Weekly: week-over-week series
- Monthly: month-over-month series

Lee desde serving facts existentes (ops.real_business_slice_*_fact).
NO crea nuevas materialized views.
NO usa raw tables desde frontend.

Motor: Control Foundation + Diagnostic Engine Temprano
"""
from datetime import date, timedelta
from typing import Optional, Dict, Any, List
from app.db import get_db


METRIC_MAP = {
    "trips_completed": "trips_completed",
    "revenue_yego_net": "revenue_yego_net",
    "active_drivers": "active_drivers",
    "avg_ticket": "avg_ticket",
    "trips_per_driver": "trips_per_driver",
    "cancel_rate_pct": "cancel_rate_pct",
}

FACT_TABLE = {
    "daily": "ops.real_business_slice_day_fact",
    "weekly": "ops.real_business_slice_week_fact",
    "monthly": "ops.real_business_slice_month_fact",
}

PERIOD_COLUMN = {
    "daily": "trip_date",
    "weekly": "week_start",
    "monthly": "month",
}


def get_omniview_momentum_drill(
    grain: str = "daily",
    metric_code: str = "trips_completed",
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    year: Optional[int] = None,
    weekday: Optional[int] = None,
    limit: int = 8,
) -> Dict[str, Any]:
    """
    Returns momentum comparison series for Omniview drill.

    Args:
        grain: daily | weekly | monthly
        metric_code: trips_completed | revenue_yego_net | active_drivers | avg_ticket
        country: filter country
        city: filter city
        business_slice: filter business slice
        fleet: filter fleet
        year: filter year
        weekday: for daily, filter to specific weekday (0=DOM..6=SAB). None=all.
        limit: max series length (default 8)

    Returns:
        {
            "status": "ok",
            "grain": "daily",
            "comparison_type": "same_weekday" | "week_over_week" | "month_over_month",
            "metric_code": "trips_completed",
            "series": [...],
            "meta": {...}
        }
    """
    if grain not in FACT_TABLE:
        return {"status": "error", "message": f"Invalid grain: {grain}. Use daily, weekly, or monthly."}

    metric_col = METRIC_MAP.get(metric_code, "trips_completed")
    table = FACT_TABLE[grain]
    period_col = PERIOD_COLUMN[grain]

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Build query
        conditions = []
        params = []

        if country:
            conditions.append("country = %s")
            params.append(country)
        if city:
            conditions.append("city = %s")
            params.append(city)
        if business_slice:
            conditions.append("business_slice_name = %s")
            params.append(business_slice)
        if fleet:
            conditions.append("fleet_display_name = %s")
            params.append(fleet)

        if grain == "daily" and year:
            conditions.append("EXTRACT(YEAR FROM trip_date) = %s")
            params.append(year)

            if weekday is not None:
                conditions.append("EXTRACT(DOW FROM trip_date) = %s")
                params.append(weekday)

        if grain == "weekly" and year:
            conditions.append("EXTRACT(YEAR FROM week_start) = %s")
            params.append(year)

        if grain == "monthly" and year:
            conditions.append("EXTRACT(YEAR FROM month) = %s")
            params.append(int(year))

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                {period_col}::text AS period_key,
                {period_col} AS period_date,
                COALESCE({metric_col}, 0) AS value
            FROM {table}
            WHERE {where_clause}
            ORDER BY {period_col} DESC
            LIMIT %s
        """
        params.append(limit * 3 if grain == "daily" and weekday is None else limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Build series with momentum deltas
        series = []
        for i, row in enumerate(rows):
            current_val = float(row["value"] or 0)
            period_key = row["period_key"]
            period_date = row["period_date"]

            # Compute momentum delta (i+1 is the previous chronological row since we ORDER BY DESC)
            previous_val = None
            delta_abs = None
            delta_pct = None

            if grain == "daily" and weekday is not None:
                # Same-weekday: compare with the row 1 position ahead (previous same weekday)
                if i + 1 < len(rows):
                    previous_val = float(rows[i + 1]["value"] or 0)
            elif grain == "daily":
                # Default daily: compare with previous day in the batch
                if i + 1 < len(rows):
                    previous_val = float(rows[i + 1]["value"] or 0)
            elif grain == "weekly":
                # WoW: compare with previous week
                if i + 1 < len(rows):
                    previous_val = float(rows[i + 1]["value"] or 0)
            elif grain == "monthly":
                # MoM: compare with previous month
                if i + 1 < len(rows):
                    previous_val = float(rows[i + 1]["value"] or 0)

            if previous_val is not None and previous_val > 0:
                delta_abs = round(current_val - previous_val, 2)
                delta_pct = round((delta_abs / abs(previous_val)) * 100, 2)

            # Format label
            if grain == "daily":
                label = period_date.strftime("%a %d %b").upper() if period_date else period_key
            elif grain == "weekly":
                iso = period_date.isocalendar() if period_date else None
                label = f"S{iso[1]:02d}-{iso[0]}" if iso else period_key
            else:  # monthly
                label = period_date.strftime("%b %Y") if period_date else period_key

            series.append({
                "period_key": period_key,
                "label": label,
                "value": current_val,
                "previous_value": previous_val,
                "delta_abs": delta_abs,
                "delta_pct": delta_pct,
                "severity": _classify_severity(delta_pct),
            })

        # Reverse to chronological order
        series.reverse()

        comparison_type = "same_weekday" if (grain == "daily" and weekday is not None) else \
                          "week_over_week" if grain == "weekly" else \
                          "month_over_month" if grain == "monthly" else "sequential"

        return {
            "status": "ok",
            "grain": grain,
            "comparison_type": comparison_type,
            "metric_code": metric_code,
            "series": series,
            "meta": {
                "freshness_status": "ok",
                "source": table,
                "is_partial_period": False,
                "serving_governed": True,
            },
        }
    finally:
        cursor.close()
        conn.close()


def _classify_severity(delta_pct):
    """Classify delta into severity."""
    if delta_pct is None:
        return "unknown"
    abs_delta = abs(delta_pct)
    if abs_delta > 30:
        return "critical"
    if abs_delta > 15:
        return "elevated"
    if abs_delta > 5:
        return "warning"
    return "normal"
