"""
Parser para la plantilla multi-hoja de Control Tower.

Formato soportado:
  Hoja CATALOGO: country, city, linea_negocio          (referencia, opcional)
  Hoja TRIPS:    country, city, linea_negocio, YYYY-MM...
  Hoja REVENUE:  country, city, linea_negocio, YYYY-MM...
  Hoja DRIVERS:  country, city, linea_negocio, YYYY-MM...

Salida: lista de dicts compatible con ops.plan_trips_monthly.

CT-MATCH-3: lob_base persiste el texto de linea_negocio del Excel (solo limpieza
de espacios); no se aplica taxonomía legacy en la ingesta de esta plantilla.
"""

import io
import re
import unicodedata
import logging
from datetime import date as _date
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

REQUIRED_SHEETS = {"TRIPS", "REVENUE", "DRIVERS"}
DIM_COLS = ["country", "city", "linea_negocio"]
MONTH_COL_RE = re.compile(r"^\d{4}-\d{2}$")

# LEGACY — mapeo semántico conservado por si otro flujo lo reutiliza.
# La plantilla Control Tower (parse_control_tower_template) ya NO usa estos mapas
# para lob_base; ver _normalize_lob_display_only (CT-MATCH-3).
# Claves en minúsculas sin tildes.
_PLAN_LOB_MAP: Dict[str, str] = {
    "auto regular":    "Auto Taxi",
    "autos regular":   "Auto Taxi",
    "auto taxi":       "Auto Taxi",
    "autotaxi":        "Auto Taxi",
    "taxi":            "Auto Taxi",
    "tuk tuk":         "Tuk Tuk",
    "tuk-tuk":         "Tuk Tuk",
    "tuktuk":          "Tuk Tuk",
    "delivery":        "Delivery",
    "moto":            "Moto Taxi",
    "moto taxi":       "Moto Taxi",
    "mototaxi":        "Moto Taxi",
    "carga":           "Carga",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _remove_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _normalize_lob(linea: str) -> str:
    """
    LEGACY: mapeo semántico (data_contract + _PLAN_LOB_MAP).
    No usado en la ingesta de plantilla Control Tower desde CT-MATCH-3.
    """
    if not linea:
        return linea
    key = _remove_accents(linea.strip().lower())
    try:
        from app.contracts.data_contract import normalize_line_of_business
        mapped = normalize_line_of_business(linea)
        if mapped and mapped.strip().lower() != linea.strip().lower():
            return mapped
    except Exception:
        pass
    return _PLAN_LOB_MAP.get(key, linea.strip())


def _normalize_lob_display_only(linea: object) -> Optional[str]:
    """
    Solo limpieza de formato para lob_base al ingerir plantilla Control Tower.

    - trim, NBSP → espacio, colapso de espacios Unicode.
    - Se preserva la capitalización y el significado del Excel (CT-MATCH-3).
    """
    if linea is None:
        return None
    try:
        if pd.isna(linea):
            return None
    except TypeError:
        pass
    s = str(linea).replace("\u00a0", " ").strip()
    if not s or s.lower() == "nan":
        return None
    s = re.sub(r"\s+", " ", s)
    return s or None


# ---------------------------------------------------------------------------
# Detección de formato
# ---------------------------------------------------------------------------

def is_control_tower_template(file_content: bytes, filename: str) -> bool:
    """
    Retorna True si el Excel contiene las hojas TRIPS, REVENUE y DRIVERS
    (formato plantilla Control Tower multi-hoja).
    """
    fn = (filename or "").lower()
    if not fn.endswith((".xlsx", ".xls")):
        return False
    try:
        xl = pd.ExcelFile(io.BytesIO(file_content))
        sheet_names_upper = {s.strip().upper() for s in xl.sheet_names}
        return REQUIRED_SHEETS.issubset(sheet_names_upper)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

def parse_control_tower_template(
    file_content: bytes,
    filename: str,
) -> Tuple[List[Dict], List[str]]:
    """
    Parsea la plantilla multi-hoja y retorna (rows, warnings).

    rows     → lista de dicts con columnas long-format listas para insertar
    warnings → advertencias no fatales (combos sin revenue/drivers)
    """
    xl = pd.ExcelFile(io.BytesIO(file_content))
    # Mapa nombre-en-Excel → nombre-en-mayúsculas (permite hojas con espacios, minúsculas...)
    sheet_map: Dict[str, str] = {s.strip().upper(): s for s in xl.sheet_names}

    warnings_list: List[str] = []

    # ── Lectura de hojas ──────────────────────────────────────────────────

    def read_sheet(canonical: str) -> pd.DataFrame:
        real_name = sheet_map[canonical]
        df = xl.parse(real_name)
        df.columns = [str(c).strip() for c in df.columns]
        missing_dims = [c for c in DIM_COLS if c not in df.columns]
        if missing_dims:
            raise ValueError(
                f"Hoja {canonical}: faltan columnas dimensionales: {missing_dims}. "
                f"Columnas encontradas: {list(df.columns)}"
            )
        return df

    try:
        df_trips   = read_sheet("TRIPS")
        df_revenue = read_sheet("REVENUE")
        df_drivers = read_sheet("DRIVERS")
    except KeyError as exc:
        raise ValueError(f"Hoja requerida no encontrada: {exc}") from exc

    # ── Detectar columnas de mes ──────────────────────────────────────────

    def get_month_cols(df: pd.DataFrame) -> List[str]:
        return [c for c in df.columns if MONTH_COL_RE.match(str(c))]

    trips_months = get_month_cols(df_trips)
    if not trips_months:
        raise ValueError(
            "Hoja TRIPS: no se encontraron columnas de mes. "
            "El formato esperado es YYYY-MM (ej: 2026-01)."
        )

    # ── Melt / unpivot ────────────────────────────────────────────────────

    def melt_sheet(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
        months = get_month_cols(df)
        if not months:
            # Hoja sin meses: retorna DataFrame vacío con schema esperado
            return pd.DataFrame(columns=DIM_COLS + ["period_month", value_name])
        keep = DIM_COLS + months
        # Ignorar columnas extra no reconocidas
        melted = df[keep].melt(
            id_vars=DIM_COLS,
            value_vars=months,
            var_name="period_month",
            value_name=value_name,
        )
        melted[value_name] = pd.to_numeric(melted[value_name], errors="coerce")
        return melted

    df_t = melt_sheet(df_trips,   "trips_plan")
    df_r = melt_sheet(df_revenue, "revenue_plan")
    df_d = melt_sheet(df_drivers, "active_drivers_plan")

    # ── Join por dimensiones ──────────────────────────────────────────────

    merge_keys = DIM_COLS + ["period_month"]
    df = (
        df_t
        .merge(df_r, on=merge_keys, how="left")
        .merge(df_d, on=merge_keys, how="left")
    )

    # ── Warnings: combos sin revenue o drivers ────────────────────────────

    no_rev = df[df["revenue_plan"].isna()]["linea_negocio"].unique().tolist()
    if no_rev:
        warnings_list.append(
            f"Combinaciones sin revenue_plan (se dejará NULL): {no_rev}"
        )
    no_drv = df[df["active_drivers_plan"].isna()]["linea_negocio"].unique().tolist()
    if no_drv:
        warnings_list.append(
            f"Combinaciones sin active_drivers_plan (se dejará NULL): {no_drv}"
        )

    # ── Derivar columnas ──────────────────────────────────────────────────

    df["year"]  = df["period_month"].str[:4].astype(int)
    df["month"] = df["period_month"].str[5:7].astype(int)

    # avg_ticket = revenue / trips (solo cuando trips > 0)
    df["avg_ticket_plan"] = None
    mask = (
        df["trips_plan"].notna()
        & (df["trips_plan"] > 0)
        & df["revenue_plan"].notna()
    )
    df.loc[mask, "avg_ticket_plan"] = (
        df.loc[mask, "revenue_plan"] / df.loc[mask, "trips_plan"]
    )

    # lob_base = literal Excel (solo limpieza de espacios; CT-MATCH-3)
    df["lob_base"] = df["linea_negocio"].apply(_normalize_lob_display_only)

    # Filtrar filas sin trips (nulos o cero)
    df = df[df["trips_plan"].notna() & (df["trips_plan"] > 0)].copy()

    if df.empty:
        raise ValueError(
            "No se encontraron filas válidas en la hoja TRIPS. "
            "Revisa que las columnas de mes tengan valores numéricos mayores a 0."
        )

    # ── Convertir a lista de dicts ────────────────────────────────────────

    rows: List[Dict] = []
    for _, row in df.iterrows():
        def safe_str(v) -> Optional[str]:
            return str(v).strip() if pd.notna(v) else None

        def safe_int(v) -> Optional[int]:
            try:
                return int(float(v)) if pd.notna(v) else None
            except (TypeError, ValueError):
                return None

        def safe_float(v) -> Optional[float]:
            try:
                return float(v) if pd.notna(v) else None
            except (TypeError, ValueError):
                return None

        rows.append({
            "country":              safe_str(row["country"]),
            "city":                 safe_str(row["city"]),
            "lob_base":             safe_str(row["lob_base"]),
            "segment":              None,   # plantilla agregada; sin desglose b2b/b2c
            "year":                 int(row["year"]),
            "month":                int(row["month"]),
            "trips_plan":           safe_int(row["trips_plan"]),
            "active_drivers_plan":  safe_int(row.get("active_drivers_plan")),
            "revenue_plan":         safe_float(row.get("revenue_plan")),
            "avg_ticket_plan":      safe_float(row.get("avg_ticket_plan")),
        })

    logger.info(
        "parse_control_tower_template: %d filas generadas, %d advertencias",
        len(rows), len(warnings_list),
    )
    return rows, warnings_list


# ---------------------------------------------------------------------------
# Inserción directa en ops.plan_trips_monthly
# ---------------------------------------------------------------------------

def ingest_control_tower_rows(rows: List[Dict], plan_version: str) -> Tuple[str, int]:
    """
    Inserta las filas del parser multi-hoja en ops.plan_trips_monthly.

    Optimización batch:
    - Pre-carga plan_city_map completo en memoria (1 query).
    - Usa executemany con una lista de tuplas (1 round-trip a la DB).
    Genera versión única si ya existe (sufijo _2, _3...).
    Retorna (final_plan_version, rows_inserted).
    """
    from app.db.connection import get_db, init_db_pool

    init_db_pool()

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Verificar que la tabla existe
            cursor.execute(
                "SELECT EXISTS("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema='ops' AND table_name='plan_trips_monthly'"
                ")"
            )
            if not cursor.fetchone()[0]:
                raise RuntimeError("Tabla ops.plan_trips_monthly no existe. Ejecuta la migración primero.")

            # Garantizar unicidad de versión (evitar plan_version duplicada)
            cursor.execute(
                "SELECT COUNT(*) FROM ops.plan_trips_monthly WHERE plan_version = %s",
                (plan_version,),
            )
            if cursor.fetchone()[0] > 0:
                suffix = 2
                while True:
                    candidate = f"{plan_version}_{suffix}"
                    cursor.execute(
                        "SELECT COUNT(*) FROM ops.plan_trips_monthly WHERE plan_version = %s",
                        (candidate,),
                    )
                    if cursor.fetchone()[0] == 0:
                        plan_version = candidate
                        break
                    suffix += 1

            # ── Pre-carga city_map (1 query, evita N round-trips) ────────────
            city_map: Dict[tuple, str] = {}
            try:
                cursor.execute(
                    """
                    SELECT country, plan_city_norm, real_city_norm
                    FROM ops.plan_city_map
                    WHERE is_active = TRUE AND real_city_norm IS NOT NULL
                    """
                )
                for country_val, plan_norm, real_norm in cursor.fetchall():
                    city_map[(country_val, plan_norm)] = real_norm
            except Exception as exc:
                logger.warning("ingest_control_tower_rows: no se pudo cargar plan_city_map — %s", exc)

            # ── Preparar batch de tuplas ──────────────────────────────────────
            batch: list = []
            skipped = 0

            for row in rows:
                try:
                    month_date = _date(row["year"], row["month"], 1)
                    city_raw   = row.get("city")
                    city_norm  = city_raw.lower().strip() if city_raw else None

                    # Lookup en el mapa precargado (sin query adicional)
                    plan_city_resolved_norm: Optional[str] = None
                    if row.get("country") and city_norm:
                        plan_city_resolved_norm = city_map.get((row["country"], city_norm))

                    batch.append((
                        plan_version,
                        row.get("country"),
                        city_raw,
                        city_norm,
                        plan_city_resolved_norm,
                        None,                        # park_id (no en plantilla)
                        row.get("lob_base"),
                        row.get("segment"),          # NULL para plantilla agregada
                        month_date,
                        row.get("trips_plan"),
                        row.get("active_drivers_plan"),
                        row.get("avg_ticket_plan"),
                        row.get("revenue_plan"),
                    ))
                except Exception as exc:
                    logger.warning("ingest_control_tower_rows: fila ignorada al preparar %s — %s", row, exc)
                    skipped += 1

            if not batch:
                conn.commit()
                return plan_version, 0

            # ── Batch INSERT (1 round-trip para todas las filas) ─────────────
            from psycopg2.extras import execute_values

            execute_values(
                cursor,
                """
                INSERT INTO ops.plan_trips_monthly (
                    plan_version,
                    country, city, city_norm, plan_city_resolved_norm,
                    park_id, lob_base, segment, month,
                    projected_trips, projected_drivers,
                    projected_ticket, projected_revenue
                )
                VALUES %s
                ON CONFLICT (
                    plan_version,
                    COALESCE(country, ''),
                    COALESCE(city, ''),
                    COALESCE(park_id, '__NA__'),
                    COALESCE(lob_base, ''),
                    COALESCE(segment, ''),
                    month
                ) DO NOTHING
                """,
                batch,
                page_size=200,   # hasta 200 filas por statement; reduce round-trips
            )
            # execute_values no expone rowcount fiable en DO NOTHING; contar via SELECT
            cursor.execute(
                "SELECT COUNT(*) FROM ops.plan_trips_monthly WHERE plan_version = %s",
                (plan_version,),
            )
            inserted = cursor.fetchone()[0]

            conn.commit()
            logger.info(
                "ingest_control_tower_rows: versión=%s, insertadas=%d, omitidas_prep=%d",
                plan_version, inserted, skipped,
            )
            return plan_version, inserted

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
