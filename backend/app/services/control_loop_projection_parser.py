"""
Parser aditivo: plantilla agregada wide (hojas TRIPS / REVENUE / DRIVERS o CSV equivalente) → long.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

_MONTH_COL = re.compile(r"^\d{4}-\d{2}$")

SHEET_NAMES_TO_METRIC = {
    "trips": "trips",
    "revenue": "revenue",
    "drivers": "active_drivers",
}

ID_COL_CANDIDATES = (
    "country",
    "pais",
    "país",
    "city",
    "ciudad",
    "linea_negocio",
    "linea de negocio",
    "line_of_business",
    "lob",
)


def _norm_col(c: str) -> str:
    return str(c).strip().lower().replace("_", " ")


def _find_id_columns(columns: List[str]) -> Tuple[str, str, str]:
    by_norm = {_norm_col(c): c for c in columns}
    country_k = None
    city_k = None
    lob_k = None
    for k, v in by_norm.items():
        if k in ("country", "pais", "país"):
            country_k = v
        if k in ("city", "ciudad"):
            city_k = v
        if k in ("linea negocio", "linea de negocio", "line of business", "lob"):
            lob_k = v
    if not country_k or not city_k or not lob_k:
        raise ValueError(
            "Columnas requeridas: country, city, linea_negocio (o equivalentes). "
            f"Encontradas: {list(columns)}"
        )
    return country_k, city_k, lob_k


def _month_columns(columns: List[str]) -> List[str]:
    out = []
    for c in columns:
        s = str(c).strip()
        if _MONTH_COL.match(s):
            out.append(s)
        else:
            # Excel a veces serializa fechas; re-exportar como Timestamp
            if hasattr(c, "strftime"):
                try:
                    out.append(c.strftime("%Y-%m"))
                except Exception:
                    pass
    return sorted(set(out))


def _sheet_to_metric(sheet_name: str) -> Optional[str]:
    k = sheet_name.strip().lower()
    return SHEET_NAMES_TO_METRIC.get(k)


def parse_control_loop_excel(content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Lee Excel con hojas TRIPS, REVENUE, DRIVERS (insensible a mayúsculas).
    Retorna filas long + lista de meses detectados.
    """
    xls = pd.ExcelFile(io.BytesIO(content))
    sheet_map = {s.strip().upper(): s for s in xls.sheet_names}
    required = ["TRIPS", "REVENUE", "DRIVERS"]
    for r in required:
        if r not in sheet_map:
            raise ValueError(
                f"Excel debe contener hojas TRIPS, REVENUE, DRIVERS. Hojas: {xls.sheet_names}"
            )

    all_rows: List[Dict[str, Any]] = []
    months_union: List[str] = []

    for upper, internal in [("TRIPS", sheet_map["TRIPS"]), ("REVENUE", sheet_map["REVENUE"]), ("DRIVERS", sheet_map["DRIVERS"])]:
        metric = _sheet_to_metric(upper)
        df = pd.read_excel(io.BytesIO(content), sheet_name=internal)
        rows, months = _dataframe_to_long(df, metric)
        all_rows.extend(rows)
        months_union.extend(months)

    months_sorted = sorted(set(months_union))
    logger.info("Control Loop Excel %s: %s filas long, meses %s", filename, len(all_rows), months_sorted)
    return all_rows, months_sorted


def parse_control_loop_csv(content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """CSV con columnas country, city, linea_negocio, metric + columnas YYYY-MM."""
    df = pd.read_csv(io.BytesIO(content))
    cols = [str(c) for c in df.columns]
    by_norm = {_norm_col(c): c for c in df.columns}
    if "metric" not in by_norm:
        raise ValueError("CSV debe incluir columna 'metric' (trips|revenue|active_drivers).")
    metric_col = by_norm["metric"]
    out: List[Dict[str, Any]] = []
    months = _month_columns(cols)
    if not months:
        raise ValueError("No se detectaron columnas de mes YYYY-MM en el CSV.")
    country_k, city_k, lob_k = _find_id_columns(cols)
    for idx, row in df.iterrows():
        mraw = str(row[metric_col]).strip().lower()
        if mraw in ("trips", "trip"):
            metric = "trips"
        elif mraw in ("revenue", "ingresos"):
            metric = "revenue"
        elif mraw in ("active_drivers", "drivers", "driver"):
            metric = "active_drivers"
        else:
            logger.warning("Fila %s: metric '%s' omitida", idx + 1, mraw)
            continue
        for mo in months:
            val = row.get(mo)
            out.append(
                {
                    "country": row[country_k],
                    "city": row[city_k],
                    "linea_negocio": row[lob_k],
                    "metric": metric,
                    "period": mo,
                    "raw_value": val,
                    "source_sheet": "CSV",
                }
            )
    return out, months


def _dataframe_to_long(df: pd.DataFrame, metric: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    new_cols = []
    for c in df.columns:
        if hasattr(c, "strftime"):
            try:
                new_cols.append(c.strftime("%Y-%m"))
            except Exception:
                new_cols.append(str(c).strip())
        else:
            new_cols.append(str(c).strip())
    df.columns = new_cols
    cols = list(df.columns)
    months = _month_columns(cols)
    if not months:
        raise ValueError("No se detectaron columnas de periodo YYYY-MM.")
    country_k, city_k, lob_k = _find_id_columns(cols)
    rows: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        for mo in months:
            if mo not in df.columns:
                continue
            rows.append(
                {
                    "country": row[country_k],
                    "city": row[city_k],
                    "linea_negocio": row[lob_k],
                    "metric": metric,
                    "period": mo,
                    "raw_value": row[mo],
                    "source_sheet": metric,
                }
            )
    return rows, months


def coerce_numeric_value(raw: Any) -> float:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 0.0
    if isinstance(raw, str) and not raw.strip():
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"No numérico: {raw!r}")
