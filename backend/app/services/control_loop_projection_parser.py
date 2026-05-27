"""
Parser aditivo: plantilla agregada wide (hojas TRIPS / REVENUE / DRIVERS o CSV equivalente) → long.

Fase 0.0 — Ownership Compatibility:
  - Acepta columnas extra: Jefe Producto, Producto, estado
  - Las persiste como metadata raw en cada fila long
  - metric auto-detectable desde nombre de archivo si no viene en el CSV
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

_OWNERSHIP_COLS_RAW = ("Jefe Producto", "Producto", "estado")
_OWNERSHIP_MAP = {
    "Jefe Producto": "jefe_producto",
    "Producto": "producto",
    "estado": "estado",
}


def _norm_col(c: str) -> str:
    return str(c).strip().lower().replace("_", " ")


def _extract_ownership_metadata(row, df_columns: List[str]) -> Dict[str, Optional[str]]:
    meta: Dict[str, Optional[str]] = {}
    for raw_col, target_key in _OWNERSHIP_MAP.items():
        if raw_col in df_columns:
            val = row.get(raw_col)
            if pd.notna(val):
                s = str(val).strip()
                if s and s.lower() != "nan":
                    meta[target_key] = s
    return meta


def _infer_metric_from_filename(filename: str) -> Optional[str]:
    fn_upper = (filename or "").upper()
    if "DRIVER" in fn_upper:
        return "active_drivers"
    if "TRIP" in fn_upper:
        return "trips"
    if "REVENUE" in fn_upper:
        return "revenue"
    return None


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


def _parse_long_format(
    df: pd.DataFrame, cols: List[str], by_norm: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Formato long unificado (Fase 1.0.2):
    country | city | linea_negocio | metric | period | value | Jefe Producto | Producto | estado

    Cada fila ya está en formato long: una combinación de dimensiones + métrica + período + valor.
    No requiere expansión wide→long.
    """
    country_k, city_k, lob_k = _find_id_columns(cols)
    period_col = by_norm.get("period") or by_norm.get("periodo")
    metric_col = by_norm["metric"]
    value_col = by_norm.get("value") or by_norm.get("valor")

    rows: List[Dict[str, Any]] = []
    periods_seen: set = set()

    for idx, row in df.iterrows():
        # Metric mapping
        mraw = str(row[metric_col]).strip().lower()
        if mraw in ("trips", "trip"):
            metric = "trips"
        elif mraw in ("revenue", "ingresos"):
            metric = "revenue"
        elif mraw in ("active_drivers", "drivers", "driver"):
            metric = "active_drivers"
        else:
            logger.warning("Fila %s: metric '%s' no reconocida, omitida", idx + 1, mraw)
            continue

        # Period: YYYY-MM from period column
        period_val = str(row[period_col]).strip()
        if not _MONTH_COL.match(period_val):
            logger.warning("Fila %s: period '%s' no es YYYY-MM, omitida", idx + 1, period_val)
            continue
        periods_seen.add(period_val)

        # Value
        raw_value = row[value_col] if value_col in row.index else row.get(value_col)

        ownership = _extract_ownership_metadata(row, cols)

        row_dict: Dict[str, Any] = {
            "country": row[country_k],
            "city": row[city_k],
            "linea_negocio": row[lob_k],
            "metric": metric,
            "period": period_val,
            "raw_value": raw_value,
            "source_sheet": "CSV_LONG",
        }
        if ownership:
            row_dict.update(ownership)
        rows.append(row_dict)

    logger.info(
        "_parse_long_format: %d filas long, %d periodos detectados",
        len(rows), len(periods_seen),
    )
    return rows, sorted(periods_seen)


def parse_control_loop_csv(content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    CSV con columnas country, city, linea_negocio + formato wide (columnas YYYY-MM)
    o formato long (columnas metric + period).

    Fase 0.0: metric es opcional si se puede inferir del nombre del archivo
    (ej. archivo "DRIVERS.csv" → active_drivers).
    Columnas extra (Jefe Producto, Producto, estado) se pasan como metadata.

    Fase 1.0.2: Soporte para plantilla unificada long (metric + period + value).
    """
    df = pd.read_csv(io.BytesIO(content))
    cols = [str(c) for c in df.columns]
    by_norm = {_norm_col(c): c for c in df.columns}

    has_metric_col = "metric" in by_norm
    has_period_col = "period" in by_norm or "periodo" in by_norm
    has_value_col = "value" in by_norm or "valor" in by_norm

    # ── Detección de formato long unificado ──────────────────────────────
    if has_period_col and has_metric_col and has_value_col:
        logger.info(
            "parse_control_loop_csv: detectado formato long unificado "
            "(metric + period + value) en '%s'", filename
        )
        return _parse_long_format(df, cols, by_norm)

    # ── Formato wide legacy ─────────────────────────────────────────────
    if has_metric_col:
        metric_col = by_norm["metric"]
    else:
        inferred = _infer_metric_from_filename(filename)
        if inferred:
            logger.info(
                "parse_control_loop_csv: columna 'metric' no encontrada, "
                "inferida de nombre de archivo '%s' → %s", filename, inferred
            )
            metric_col = None
        else:
            raise ValueError(
                "CSV debe incluir columna 'metric' (trips|revenue|active_drivers). "
                "Si el archivo tiene nombre descriptivo (ej. 'DRIVERS.csv'), se intenta inferir. "
                f"Columnas encontradas: {list(cols)}"
            )

    out: List[Dict[str, Any]] = []
    months = _month_columns(cols)
    if not months:
        raise ValueError(
            "No se detectaron columnas de mes YYYY-MM en el CSV. "
            "Use formato wide (columnas 2026-01, 2026-02...) o formato long "
            "(columnas metric + period + value)."
        )
    country_k, city_k, lob_k = _find_id_columns(cols)

    implicit_metric: Optional[str] = None
    if not has_metric_col:
        implicit_metric = _infer_metric_from_filename(filename)

    for idx, row in df.iterrows():
        if has_metric_col:
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
        elif implicit_metric:
            metric = implicit_metric
        else:
            continue

        ownership = _extract_ownership_metadata(row, cols)

        for mo in months:
            val = row.get(mo)
            row_dict: Dict[str, Any] = {
                "country": row[country_k],
                "city": row[city_k],
                "linea_negocio": row[lob_k],
                "metric": metric,
                "period": mo,
                "raw_value": val,
                "source_sheet": "CSV",
            }
            if ownership:
                row_dict.update(ownership)
            out.append(row_dict)
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
        ownership = _extract_ownership_metadata(row, cols)
        for mo in months:
            if mo not in df.columns:
                continue
            row_dict: Dict[str, Any] = {
                "country": row[country_k],
                "city": row[city_k],
                "linea_negocio": row[lob_k],
                "metric": metric,
                "period": mo,
                "raw_value": row[mo],
                "source_sheet": metric,
            }
            if ownership:
                row_dict.update(ownership)
            rows.append(row_dict)
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
