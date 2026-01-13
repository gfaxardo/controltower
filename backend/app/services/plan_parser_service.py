import pandas as pd
import logging
from typing import List, Dict, Optional, Tuple
from app.services.ops_universe_service import get_ops_universe_set, is_in_universe, clear_cache
from app.contracts.data_contract import (
    normalize_line_of_business, 
    normalize_country_std, 
    normalize_city_std, 
    normalize_line_of_business_std
)
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import io
import re

logger = logging.getLogger(__name__)

def parse_simple_template(file_content: bytes, filename: str) -> List[Dict]:
    """
    Parsea una plantilla simple (CSV o XLSX) con columnas exactas:
    period, country, city, line_of_business, metric, plan_value
    
    Valida:
    - Columnas exactas requeridas
    - period formato YYYY-MM
    - metric ∈ {trips, revenue, commission, active_drivers}
    
    Retorna lista de diccionarios en formato long.
    """
    try:
        file_ext = filename.lower().split('.')[-1]
        
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(file_content))
        elif file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            raise ValueError(f"Formato de archivo no soportado: {file_ext}. Use CSV o XLSX")
        
        required_columns = {'period', 'country', 'city', 'line_of_business', 'metric', 'plan_value'}
        df_columns_lower = {col.lower().strip() for col in df.columns}
        
        missing_columns = required_columns - df_columns_lower
        if missing_columns:
            raise ValueError(f"Faltan columnas requeridas: {missing_columns}. Columnas encontradas: {list(df.columns)}")
        
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in required_columns:
                column_mapping[col_lower] = col
        
        rows_long = []
        valid_metrics = {'trips', 'revenue', 'commission', 'active_drivers'}
        period_pattern = re.compile(r'^\d{4}-\d{2}$')
        
        for idx, row in df.iterrows():
            try:
                period = str(row[column_mapping['period']]).strip()
                if not period_pattern.match(period):
                    logger.warning(f"Fila {idx + 1}: period '{period}' no tiene formato YYYY-MM, se omite")
                    continue
                
                metric = str(row[column_mapping['metric']]).strip().lower()
                if metric not in valid_metrics:
                    logger.warning(f"Fila {idx + 1}: metric '{metric}' no es válida (debe ser: {valid_metrics}), se omite")
                    continue
                
                plan_value = row[column_mapping['plan_value']]
                if pd.isna(plan_value):
                    logger.warning(f"Fila {idx + 1}: plan_value es null, se omite")
                    continue
                
                try:
                    plan_value_float = float(plan_value)
                except (ValueError, TypeError):
                    logger.warning(f"Fila {idx + 1}: plan_value '{plan_value}' no es numérico, se omite")
                    continue
                
                country = str(row[column_mapping['country']]).strip() if pd.notna(row[column_mapping['country']]) else None
                city = str(row[column_mapping['city']]).strip() if pd.notna(row[column_mapping['city']]) else None
                line_of_business_raw = str(row[column_mapping['line_of_business']]).strip() if pd.notna(row[column_mapping['line_of_business']]) else None
                line_of_business = normalize_line_of_business(line_of_business_raw) if line_of_business_raw else None
                
                registro = {
                    'period_type': 'month',
                    'period': period,
                    'country': country if country else None,
                    'city': city if city else None,
                    'line_of_business': line_of_business if line_of_business else None,
                    'metric': metric,
                    'plan_value': plan_value_float
                }
                
                rows_long.append(registro)
                
            except Exception as e:
                logger.warning(f"Error al procesar fila {idx + 1}: {e}")
                continue
        
        if not rows_long:
            raise ValueError("No se pudieron extraer datos válidos de la plantilla simple")
        
        logger.info(f"Plantilla simple parseada: {len(rows_long)} filas válidas de {len(df)} filas totales")
        return rows_long
        
    except Exception as e:
        logger.error(f"Error al parsear plantilla simple: {e}")
        raise

def parse_proyeccion_sheet_legacy(file_content: bytes, filename: str, year_default: int = 2026) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Parsea la hoja "Proyección" del Excel y separa en 3 listas:
    - valid: filas válidas (en universo operativo)
    - out_of_universe: filas fuera de universo
    - missing: combos operativos sin plan
    
    Retorna (valid_rows, out_of_universe_rows, missing_combos)
    """
    try:
        excel_file = io.BytesIO(file_content)
        xls = pd.ExcelFile(excel_file)
        
        hoja_proyeccion = None
        for sheet_name in xls.sheet_names:
            if 'proyecci' in sheet_name.lower():
                hoja_proyeccion = sheet_name
                logger.info(f"Hoja 'Proyección' encontrada: {sheet_name}")
                break
        
        if not hoja_proyeccion:
            raise ValueError("No se encontró la hoja 'Proyección' en el Excel")
        
        df = pd.read_excel(excel_file, sheet_name=hoja_proyeccion, header=None)
        logger.info(f"Excel leído de hoja '{hoja_proyeccion}': {len(df)} filas, {len(df.columns)} columnas")
        
        rows_long = _process_proyeccion_dataframe(df, year_default)
        logger.info(f"Procesadas {len(rows_long)} filas del formato Proyección")
        
        valid_rows, out_of_universe_rows = _separate_by_universe(rows_long)
        missing_combos = _find_missing_combos(valid_rows, out_of_universe_rows)
        
        return valid_rows, out_of_universe_rows, missing_combos
        
    except Exception as e:
        logger.error(f"Error al parsear hoja Proyección: {e}")
        raise

def _process_proyeccion_dataframe(df: pd.DataFrame, year_default: int) -> List[Dict]:
    """
    Procesa el DataFrame de la hoja Proyección y genera filas en formato long.
    """
    if df.empty or len(df) < 4:
        raise ValueError("El Excel de Proyección debe tener al menos 4 filas")
    
    meses_espanol = {
        'ene': 1, 'enero': 1, 'jan': 1, 'january': 1,
        'feb': 2, 'febrero': 2, 'february': 2,
        'mar': 3, 'marzo': 3, 'march': 3,
        'abr': 4, 'abril': 4, 'apr': 4, 'april': 4,
        'may': 5, 'mayo': 5,
        'jun': 6, 'junio': 6, 'june': 6,
        'jul': 7, 'julio': 7, 'july': 7,
        'ago': 8, 'agosto': 8, 'aug': 8, 'august': 8,
        'set': 9, 'sep': 9, 'septiembre': 9, 'september': 9,
        'oct': 10, 'octubre': 10, 'october': 10,
        'nov': 11, 'noviembre': 11, 'november': 11,
        'dic': 12, 'diciembre': 12, 'dec': 12, 'december': 12
    }
    
    headers_idx = None
    años_row = None
    
    for row_idx in range(2, min(5, len(df))):
        test_row = df.iloc[row_idx]
        for col_idx in range(min(10, len(test_row))):
            val = test_row.iloc[col_idx] if hasattr(test_row, 'iloc') else test_row[col_idx]
            if pd.notna(val):
                val_str = str(val).strip().lower()
                if 'ciudad' in val_str or 'servicio' in val_str:
                    headers_idx = row_idx
                    logger.info(f"Encabezados encontrados en índice {row_idx}")
                    break
        if headers_idx is not None:
            break
    
    if headers_idx is None:
        raise ValueError("No se encontró la fila de encabezados en el Excel")
    
    headers_row = df.iloc[headers_idx]
    
    for i in range(headers_idx - 1, max(-1, headers_idx - 3), -1):
        test_row = df.iloc[i]
        for col_idx in range(min(20, len(test_row))):
            val = test_row.iloc[col_idx] if hasattr(test_row, 'iloc') else test_row[col_idx]
            if pd.notna(val):
                val_str = str(val).strip()
                if val_str.isdigit() and len(val_str) == 4 and 2020 <= int(val_str) <= 2100:
                    años_row = test_row
                    logger.info(f"Años encontrados en índice {i}")
                    break
        if años_row is not None:
            break
    
    if años_row is None:
        logger.warning("No se encontraron años en el Excel, se usará el año por defecto 2026")
    
    columnas_meses = []
    ciudad_col_idx = None
    servicio_col_idx = None
    
    for col_idx in range(len(df.columns)):
        header_val = headers_row.iloc[col_idx] if hasattr(headers_row, 'iloc') else headers_row[col_idx]
        if pd.notna(header_val):
            header_str = str(header_val).strip().lower()
            if header_str in meses_espanol:
                columnas_meses.append((col_idx, header_str))
            elif 'ciudad' in header_str or 'city' in header_str:
                ciudad_col_idx = col_idx
            elif 'servicio' in header_str:
                servicio_col_idx = col_idx
    
    if not columnas_meses:
        raise ValueError("No se encontraron columnas de meses en los encabezados")
    
    logger.info(f"Columnas de meses detectadas: {len(columnas_meses)}")
    
    df_long_list = []
    país_actual = None
    métrica_actual = None
    ciudad_actual = None
    
    start_data_idx = headers_idx + 1
    
    for idx in range(start_data_idx, len(df)):
        row = df.iloc[idx]
        
        col1_val = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ''
        col2_val = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ''
        col3_val = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else ''
        
        col1_lower = col1_val.lower()
        col2_lower = col2_val.lower()
        col3_lower = col3_val.lower()
        
        if 'perú' in col1_lower or 'peru' in col1_lower:
            país_actual = 'Peru'
        elif 'colombia' in col1_lower:
            país_actual = 'Colombia'
        
        if 'ingresos' in col1_lower or 'ingreso' in col1_lower or 'revenue' in col1_lower:
            métrica_actual = 'revenue'
        elif 'viajes' in col1_lower or 'viaje' in col1_lower or 'trips' in col1_lower or 'trip' in col1_lower:
            métrica_actual = 'trips'
        elif 'ingresos' in col2_lower or 'ingreso' in col2_lower:
            métrica_actual = 'revenue'
        elif 'viajes' in col2_lower or 'viaje' in col2_lower:
            métrica_actual = 'trips'
        
        if not país_actual or not métrica_actual:
            continue
        
        es_total = 'total' in col2_lower or 'total' in col3_lower
        
        if not es_total:
            ciudades_conocidas = ['lima', 'trujillo', 'arequipa', 'chiclayo', 'piura', 'cusco', 'huancayo',
                                 'bogotá', 'bogota', 'medellín', 'medellin', 'cali', 'barranquilla']
            for ciudad in ciudades_conocidas:
                if ciudad in col2_lower:
                    ciudad_actual = col2_val
                    break
                elif ciudad in col3_lower:
                    ciudad_actual = col3_val
                    break
            
            if ciudad_col_idx and servicio_col_idx:
                if pd.notna(row.iloc[ciudad_col_idx]):
                    ciudad_actual = str(row.iloc[ciudad_col_idx]).strip()
                servicio_en_fila = str(row.iloc[servicio_col_idx]).strip() if pd.notna(row.iloc[servicio_col_idx]) else None
            else:
                if ciudad_actual == col2_val and pd.notna(row.iloc[3]) and str(row.iloc[3]).strip().lower() not in ciudades_conocidas:
                    servicio_en_fila = str(row.iloc[3]).strip()
                elif not ciudad_actual and pd.notna(row.iloc[3]):
                    servicio_en_fila = str(row.iloc[3]).strip() if str(row.iloc[3]).strip().lower() not in ciudades_conocidas else None
                else:
                    servicio_en_fila = None
        else:
            servicio_en_fila = None
        
        for col_idx, mes_nombre in columnas_meses:
            if col_idx >= len(row):
                continue
            
            valor = row.iloc[col_idx]
            if pd.isna(valor) or valor == 0:
                continue
            
            try:
                plan_value_float = float(valor)
                if plan_value_float == 0:
                    continue
                
                año = _extract_year_from_column(col_idx, años_row, year_default) if años_row is not None else year_default
                mes_num = meses_espanol.get(mes_nombre, None)
                if not mes_num:
                    continue
                
                period = f"{año}-{mes_num:02d}"
                
                registro = {
                    'period_type': 'month',
                    'period': period,
                    'country': país_actual,
                    'city': None if es_total else ciudad_actual,
                    'line_of_business': None if es_total else servicio_en_fila,
                    'metric': métrica_actual,
                    'plan_value': plan_value_float
                }
                
                df_long_list.append(registro)
                
            except (ValueError, TypeError):
                continue
    
    if not df_long_list:
        raise ValueError("No se pudieron extraer datos del Excel en formato Proyección")
    
    return df_long_list

def _extract_year_from_column(col_idx: int, años_row: pd.Series, año_default: int) -> int:
    """Extrae el año al que pertenece una columna basándose en la fila de años."""
    if años_row is None or len(años_row) == 0:
        return año_default
    
    años_detectados = []
    for idx in range(len(años_row)):
        val = años_row.iloc[idx] if hasattr(años_row, 'iloc') else años_row[idx]
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str.isdigit() and len(val_str) == 4:
                año = int(val_str)
                if 2020 <= año <= 2100:
                    años_detectados.append((idx, año))
    
    if not años_detectados:
        return año_default
    
    años_detectados.sort()
    año_actual = año_default
    for col_idx_año, año in años_detectados:
        if col_idx >= col_idx_año:
            año_actual = año
        else:
            break
    
    return año_actual

def _get_ingestion_status() -> Dict:
    """
    Obtiene el estado de ingesta desde bi.ingestion_status.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT dataset_name, max_year, max_month, last_loaded_at, is_complete_2025
                FROM bi.ingestion_status
                WHERE dataset_name = 'real_monthly_agg'
            """)
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return dict(result)
            else:
                return {
                    "dataset_name": "real_monthly_agg",
                    "max_year": 2025,
                    "max_month": 0,
                    "is_complete_2025": False
                }
    except Exception as e:
        logger.warning(f"Error al obtener estado de ingesta, usando valores por defecto: {e}")
        return {
            "dataset_name": "real_monthly_agg",
            "max_year": 2025,
            "max_month": 0,
            "is_complete_2025": False
        }

def _get_universe_countries() -> set:
    """
    Obtiene el set de países normalizados del universo.
    """
    from app.adapters.real_repo import get_ops_universe_data
    universe = get_ops_universe_data()
    return {row.get('country_std', '') for row in universe if row.get('country_std')}

def _separate_by_universe(rows: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Separa las filas en válidas (en universo) y fuera de universo.
    Usa claves canónicas normalizadas (_std) para comparaciones.
    Asigna reason según el caso.
    """
    valid_rows = []
    out_of_universe_rows = []
    
    universe_set = get_ops_universe_set()
    ingestion_status = _get_ingestion_status()
    is_complete_2025 = ingestion_status.get('is_complete_2025', False)
    universe_countries = _get_universe_countries()
    
    for row in rows:
        country_raw = row.get('country', '') or ''
        city_raw = row.get('city', '') or ''
        line_of_business_raw = row.get('line_of_business', '') or ''
        
        # Normalizar a claves canónicas para comparación
        country_std = normalize_country_std(country_raw)
        city_std = normalize_city_std(city_raw)
        line_of_business_std = normalize_line_of_business_std(line_of_business_raw)
        
        # Mantener formato humano para UI
        line_of_business_human = normalize_line_of_business(line_of_business_raw) if line_of_business_raw else None
        
        # Validar campos requeridos
        if not city_raw or not line_of_business_raw:
            row_with_reason = row.copy()
            reason_value = 'MISSING_CITY_IN_UNIVERSE' if not city_raw else 'UNMAPPED_LINE'
            row_with_reason['reason'] = reason_value
            if 'reason' not in row_with_reason:
                logger.warning(f"ADVERTENCIA: reason no se agregó correctamente a la fila")
            out_of_universe_rows.append(row_with_reason)
            continue
        
        # Comparar usando claves canónicas
        combo_std = (country_std, city_std, line_of_business_std)
        
        if combo_std in universe_set:
            # VALID: está en universo observado
            row_normalized = row.copy()
            row_normalized['line_of_business'] = line_of_business_human
            valid_rows.append(row_normalized)
        else:
            # OUT_OF_UNIVERSE: determinar reason
            row_with_reason = row.copy()
            reason = None
            
            # Prioridad 1: UNMAPPED_COUNTRY
            if country_std and country_std not in universe_countries:
                reason = 'UNMAPPED_COUNTRY'
            # Prioridad 2: UNMAPPED_LINE (si la línea no se puede mapear)
            elif not line_of_business_human or line_of_business_human == line_of_business_raw:
                # Si no hay mapeo, podría ser línea no mapeable
                reason = 'UNMAPPED_LINE'
            # Prioridad 3: NOT_IN_UNIVERSE_YET o LIKELY_EXPANSION
            elif not is_complete_2025:
                reason = 'NOT_IN_UNIVERSE_YET'
            else:
                reason = 'LIKELY_EXPANSION'
            
            if not reason:
                reason = 'UNKNOWN_REASON'
            
            row_with_reason['reason'] = reason
            if 'reason' not in row_with_reason:
                logger.error(f"ERROR CRÍTICO: reason no se agregó a la fila después de asignación")
            out_of_universe_rows.append(row_with_reason)
    
    logger.info(f"Separadas {len(valid_rows)} filas válidas y {len(out_of_universe_rows)} fuera de universo (is_complete_2025={is_complete_2025})")
    return valid_rows, out_of_universe_rows

def _find_missing_combos(valid_rows: List[Dict], out_of_universe_rows: List[Dict]) -> List[Dict]:
    """
    Encuentra combinaciones operativas que no tienen plan.
    Usa claves canónicas normalizadas para comparación.
    """
    from app.services.ops_universe_service import get_ops_universe
    universe_list = get_ops_universe()  # Obtener lista completa con valores humanos
    universe_set = get_ops_universe_set()  # Set normalizado para comparación
    plan_combos = set()
    
    for row in valid_rows:
        # Normalizar para comparación
        country_std = normalize_country_std(row.get('country', '') or '')
        city_std = normalize_city_std(row.get('city', '') or '')
        line_std = normalize_line_of_business_std(row.get('line_of_business', '') or '')
        combo_std = (country_std, city_std, line_std)
        if city_std and line_std:
            plan_combos.add(combo_std)
    
    # Crear mapa de combo_std -> valores humanos
    universe_map = {}
    for row in universe_list:
        combo_std = (
            row.get('country_std', ''),
            row.get('city_std', ''),
            row.get('line_of_business_std', '')
        )
        universe_map[combo_std] = {
            'country': row.get('country', ''),
            'city': row.get('city', ''),
            'line_of_business': row.get('line_of_business', '')
        }
    
    missing_combos = []
    metrics = ['trips', 'revenue']
    for combo_std in universe_set:
        if combo_std not in plan_combos:
            human_values = universe_map.get(combo_std, {})
            for metric in metrics:
                missing_combos.append({
                    'period_type': 'month',
                    'period': None,
                    'country': human_values.get('country', ''),
                    'city': human_values.get('city', ''),
                    'line_of_business': human_values.get('line_of_business', ''),
                    'metric': metric
                })
    
    logger.info(f"Encontrados {len(missing_combos)} combos operativos sin plan")
    return missing_combos

