"""
Script de diagnóstico para auditar public.trips_all y proponer contrato REAL.

PASO A: Auditoría completa sin modificar datos.
OBJETIVO: Identificar campos candidatos para el contrato REAL (status, driver_id, fecha, monto).
"""

import sys
import os
import io

# Configurar codificación UTF-8 para salida
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from collections import defaultdict
import json

def safe_execute(cursor, query, description=""):
    """Ejecuta una consulta de forma segura y retorna resultados."""
    try:
        cursor.execute(query)
        return cursor.fetchall()
    except Exception as e:
        print(f"  [WARN] Error en {description}: {e}")
        return []

def get_column_info(cursor):
    """Obtiene información completa de columnas de public.trips_all."""
    query = """
        SELECT 
            column_name, 
            data_type, 
            is_nullable,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'trips_all'
        ORDER BY ordinal_position
    """
    return safe_execute(cursor, query, "obtener columnas")

def get_table_count(cursor):
    """Obtiene el total de registros en la tabla."""
    query = "SELECT COUNT(*) FROM public.trips_all"
    result = safe_execute(cursor, query, "contar registros")
    return result[0][0] if result else 0

def find_status_candidates(cursor, columns):
    """Encuentra columnas candidatas para status."""
    candidates = []
    for col_name, data_type, is_nullable, max_length in columns:
        col_lower = col_name.lower()
        if data_type in ('text', 'character varying', 'varchar') and any(
            keyword in col_lower for keyword in ['status', 'state', 'order_status', 'trip_status', 'condicion', 'estado']
        ):
            candidates.append({
                'column': col_name,
                'type': data_type,
                'nullable': is_nullable
            })
    return candidates

def analyze_status_values(cursor, column_name, total_rows):
    """Analiza valores distintos de una columna de status."""
    query = f"""
        SELECT {column_name}, COUNT(*) as cnt
        FROM public.trips_all
        WHERE {column_name} IS NOT NULL
        GROUP BY {column_name}
        ORDER BY cnt DESC
        LIMIT 50
    """
    results = safe_execute(cursor, query, f"analizar valores de {column_name}")
    
    # Calcular nulos
    null_query = f"SELECT COUNT(*) FROM public.trips_all WHERE {column_name} IS NULL"
    null_result = safe_execute(cursor, null_query, f"contar nulos en {column_name}")
    null_count = null_result[0][0] if null_result else 0
    null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
    
    return {
        'values': [(val, cnt) for val, cnt in results],
        'null_count': null_count,
        'null_pct': null_pct,
        'distinct_count': len(results)
    }

def find_driver_candidates(cursor, columns):
    """Encuentra columnas candidatas para driver_id."""
    candidates = []
    for col_name, data_type, is_nullable, max_length in columns:
        col_lower = col_name.lower()
        if ('driver' in col_lower or 'conductor' in col_lower) and ('id' in col_lower or data_type in ('integer', 'bigint', 'uuid', 'text', 'character varying')):
            candidates.append({
                'column': col_name,
                'type': data_type,
                'nullable': is_nullable
            })
    return candidates

def analyze_driver_field(cursor, column_name, total_rows):
    """Analiza un campo de driver: nulos, distinct count."""
    # Nulos
    null_query = f"SELECT COUNT(*) FROM public.trips_all WHERE {column_name} IS NULL"
    null_result = safe_execute(cursor, null_query, f"contar nulos en {column_name}")
    null_count = null_result[0][0] if null_result else 0
    null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
    
    # Distinct
    distinct_query = f"SELECT COUNT(DISTINCT {column_name}) FROM public.trips_all WHERE {column_name} IS NOT NULL"
    distinct_result = safe_execute(cursor, distinct_query, f"contar distinct en {column_name}")
    distinct_count = distinct_result[0][0] if distinct_result else 0
    
    return {
        'null_count': null_count,
        'null_pct': null_pct,
        'distinct_count': distinct_count
    }

def find_date_candidates(cursor, columns):
    """Encuentra columnas candidatas para fecha canónica."""
    candidates = []
    for col_name, data_type, is_nullable, max_length in columns:
        col_lower = col_name.lower()
        if data_type in ('timestamp without time zone', 'timestamp with time zone', 'date', 'timestamp'):
            # Priorizar nombres específicos
            priority = 0
            if any(name in col_lower for name in ['start', 'begin', 'fecha_inicio', 'inicio']):
                priority = 1
            elif any(name in col_lower for name in ['completed', 'end', 'final']):
                priority = 2
            elif 'created' in col_lower:
                priority = 3
            elif 'date' in col_lower or 'fecha' in col_lower:
                priority = 4
            
            candidates.append({
                'column': col_name,
                'type': data_type,
                'nullable': is_nullable,
                'priority': priority
            })
    
    # Ordenar por prioridad
    candidates.sort(key=lambda x: x['priority'])
    return candidates

def analyze_date_field(cursor, column_name, total_rows, status_column=None, completed_value=None):
    """Analiza un campo de fecha: min/max, nulos, correlación con status."""
    # Nulos
    null_query = f"SELECT COUNT(*) FROM public.trips_all WHERE {column_name} IS NULL"
    null_result = safe_execute(cursor, null_query, f"contar nulos en {column_name}")
    null_count = null_result[0][0] if null_result else 0
    null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
    
    # Min/Max
    min_query = f"SELECT MIN({column_name}) FROM public.trips_all WHERE {column_name} IS NOT NULL"
    max_query = f"SELECT MAX({column_name}) FROM public.trips_all WHERE {column_name} IS NOT NULL"
    min_result = safe_execute(cursor, min_query, f"min de {column_name}")
    max_result = safe_execute(cursor, max_query, f"max de {column_name}")
    min_val = min_result[0][0] if min_result and min_result[0][0] else None
    max_val = max_result[0][0] if max_result and max_result[0][0] else None
    
    # Si hay status column, calcular correlación
    completed_count = None
    if status_column and completed_value:
        corr_query = f"""
            SELECT COUNT(*) 
            FROM public.trips_all 
            WHERE {status_column} = %s AND {column_name} IS NOT NULL
        """
        try:
            cursor.execute(corr_query, (completed_value,))
            result = cursor.fetchone()
            completed_count = result[0] if result else None
        except:
            pass
    
    return {
        'null_count': null_count,
        'null_pct': null_pct,
        'min': min_val,
        'max': max_val,
        'completed_count': completed_count
    }

def find_amount_candidates(cursor, columns):
    """Encuentra columnas candidatas para monto/ticket."""
    candidates = []
    keywords = ['amount', 'fare', 'price', 'total', 'cost', 'tarifa', 'monto', 'ticket', 'precio', 'pago', 'efectivo', 'tarjeta']
    
    for col_name, data_type, is_nullable, max_length in columns:
        col_lower = col_name.lower()
        if data_type in ('numeric', 'real', 'double precision', 'integer', 'bigint', 'money'):
            if any(keyword in col_lower for keyword in keywords):
                # Excluir campos muy específicos como propina, comisión, etc. a menos que no haya otros candidatos
                if not any(exclude in col_lower for exclude in ['propina', 'promocion', 'bonificacion', 'comision']):
                    candidates.append({
                        'column': col_name,
                        'type': data_type,
                        'nullable': is_nullable
                    })
                elif not candidates:  # Si no hay candidatos, incluir también estos
                    candidates.append({
                        'column': col_name,
                        'type': data_type,
                        'nullable': is_nullable
                    })
    return candidates

def analyze_amount_field(cursor, column_name, total_rows):
    """Analiza un campo de monto: min/max, percentiles, nulos."""
    # Nulos
    null_query = f"SELECT COUNT(*) FROM public.trips_all WHERE {column_name} IS NULL"
    null_result = safe_execute(cursor, null_query, f"contar nulos en {column_name}")
    null_count = null_result[0][0] if null_result else 0
    null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
    
    # Estadísticas
    stats_query = f"""
        SELECT 
            MIN({column_name}) as min_val,
            MAX({column_name}) as max_val,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY {column_name}) as p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {column_name}) as p95,
            AVG({column_name}) as avg_val
        FROM public.trips_all
        WHERE {column_name} IS NOT NULL
    """
    stats_result = safe_execute(cursor, stats_query, f"estadísticas de {column_name}")
    
    if stats_result and stats_result[0]:
        row = stats_result[0]
        return {
            'null_count': null_count,
            'null_pct': null_pct,
            'min': row[0],
            'max': row[1],
            'p50': row[2],
            'p95': row[3],
            'avg': row[4]
        }
    
    return {
        'null_count': null_count,
        'null_pct': null_pct,
        'min': None,
        'max': None,
        'p50': None,
        'p95': None,
        'avg': None
    }

def find_related_tables(cursor):
    """Busca tablas relacionadas que puedan tener información de monto."""
    # Buscar tablas con nombres relacionados
    query = """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
        AND (
            table_name LIKE '%fare%' OR
            table_name LIKE '%price%' OR
            table_name LIKE '%payment%' OR
            table_name LIKE '%billing%' OR
            table_name LIKE '%order%' OR
            table_name LIKE '%transaction%'
        )
        ORDER BY table_schema, table_name
    """
    tables = safe_execute(cursor, query, "buscar tablas relacionadas")
    
    # Para cada tabla, buscar columnas de monto y posibles FKs
    related_info = []
    for schema, table_name in tables:
        # Columnas de monto
        cols_query = f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            AND (
                column_name LIKE '%amount%' OR
                column_name LIKE '%fare%' OR
                column_name LIKE '%price%' OR
                column_name LIKE '%total%' OR
                column_name LIKE '%cost%'
            )
        """
        try:
            cursor.execute(cols_query, (schema, table_name))
            amount_cols = cursor.fetchall()
        except:
            amount_cols = []
        
        # Buscar posibles FKs o columnas que puedan relacionarse con trips
        fk_query = f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            AND (
                column_name LIKE '%trip%' OR
                column_name LIKE '%order%' OR
                column_name LIKE '%pedido%' OR
                column_name LIKE '%id%'
            )
        """
        try:
            cursor.execute(fk_query, (schema, table_name))
            key_cols = cursor.fetchall()
        except:
            key_cols = []
        
        if amount_cols or key_cols:
            related_info.append({
                'schema': schema,
                'table': table_name,
                'amount_columns': [{'name': c[0], 'type': c[1]} for c in amount_cols],
                'key_columns': [{'name': c[0], 'type': c[1]} for c in key_cols]
            })
    
    return related_info

def generate_report(cursor):
    """Genera el reporte completo de diagnóstico."""
    print("\n" + "="*80)
    print("AUDITORÍA DE public.trips_all - CONTRATO REAL")
    print("="*80 + "\n")
    
    # 1. Información general
    print("## 1. INFORMACIÓN GENERAL\n")
    columns = get_column_info(cursor)
    total_rows = get_table_count(cursor)
    print(f"**Total de columnas:** {len(columns)}")
    print(f"**Total de registros:** {total_rows:,}")
    print(f"**Esquema:** public")
    print(f"**Tabla:** trips_all\n")
    
    # Listar todas las columnas
    print("**Lista completa de columnas:**\n")
    print("| Columna | Tipo de Dato | Nullable |")
    print("|---------|--------------|----------|")
    for col_name, data_type, is_nullable, max_length in columns:
        nullable_str = "Sí" if is_nullable == 'YES' else "No"
        type_str = f"{data_type}({max_length})" if max_length else data_type
        print(f"| `{col_name}` | {type_str} | {nullable_str} |")
    print()
    
    # A) Diccionario de campos candidatos
    print("## A) DICCIONARIO DE CAMPOS CANDIDATOS\n")
    
    # STATUS
    print("### STATUS (Estado del viaje)\n")
    status_candidates = find_status_candidates(cursor, columns)
    if status_candidates:
        for cand in status_candidates:
            print(f"- **{cand['column']}** ({cand['type']}, nullable: {cand['nullable']})")
    else:
        print("- [WARN] No se encontraron columnas candidatas para status")
    print()
    
    # DRIVER
    print("### DRIVER_ID (Identificador del conductor)\n")
    driver_candidates = find_driver_candidates(cursor, columns)
    if driver_candidates:
        for cand in driver_candidates:
            print(f"- **{cand['column']}** ({cand['type']}, nullable: {cand['nullable']})")
    else:
        print("- [WARN] No se encontraron columnas candidatas para driver_id")
    print()
    
    # DATE
    print("### TRIP_DATETIME (Fecha canónica del viaje)\n")
    date_candidates = find_date_candidates(cursor, columns)
    if date_candidates:
        for cand in date_candidates:
            priority_name = ['Alta', 'Media-alta', 'Media', 'Baja', 'Muy baja'][cand['priority']] if cand['priority'] <= 4 else 'N/A'
            print(f"- **{cand['column']}** ({cand['type']}, nullable: {cand['nullable']}, prioridad: {priority_name})")
    else:
        print("- [WARN] No se encontraron columnas candidatas para fecha")
    print()
    
    # AMOUNT
    print("### TRIP_AMOUNT (Monto/Ticket del viaje)\n")
    amount_candidates = find_amount_candidates(cursor, columns)
    if amount_candidates:
        for cand in amount_candidates:
            print(f"- **{cand['column']}** ({cand['type']}, nullable: {cand['nullable']})")
    else:
        print("- [WARN] No se encontraron columnas candidatas para monto en trips_all")
    print()
    
    # B) Tabla de valores distintos para status
    print("## B) ANÁLISIS DE STATUS\n")
    status_column = None
    completed_value = None
    
    if status_candidates:
        # Analizar la primera candidata (o la más prometedora)
        status_column = status_candidates[0]['column']
        status_analysis = analyze_status_values(cursor, status_column, total_rows)
        
        print(f"**Columna analizada:** `{status_column}`\n")
        print(f"**Valores distintos:** {status_analysis['distinct_count']}")
        print(f"**Valores nulos:** {status_analysis['null_count']:,} ({status_analysis['null_pct']:.2f}%)\n")
        
        print("**Top 20 valores por frecuencia:**\n")
        print("| Valor | Conteo | % del Total |")
        print("|-------|--------|-------------|")
        for val, cnt in status_analysis['values'][:20]:
            pct = (cnt / total_rows * 100) if total_rows > 0 else 0
            val_str = str(val)[:50] if val else 'NULL'
            print(f"| {val_str} | {cnt:,} | {pct:.2f}% |")
        
        # Buscar valores que contengan "COMPLET" o similares
        print("\n**Valores que contienen 'COMPLET', 'FINALIZ', 'TERMIN' o similares:**\n")
        completed_candidates = [(val, cnt) for val, cnt in status_analysis['values'] 
                               if val and any(term in str(val).lower() for term in ['complet', 'finaliz', 'termin', 'final', 'done', 'ok', 'exitoso'])]
        if completed_candidates:
            for val, cnt in completed_candidates:
                pct = (cnt / total_rows * 100) if total_rows > 0 else 0
                print(f"- `{val}`: {cnt:,} registros ({pct:.2f}%)")
                if not completed_value or cnt > completed_candidates[0][1]:
                    completed_value = val
        else:
            print("- No se encontraron valores con 'COMPLET'")
    else:
        print("[WARN] No hay columnas de status para analizar")
    print()
    
    # C) % nulos para driver_id y campos clave
    print("## C) ANÁLISIS DE NULOS EN CAMPOS CLAVE\n")
    if driver_candidates:
        for cand in driver_candidates:
            driver_analysis = analyze_driver_field(cursor, cand['column'], total_rows)
            print(f"**{cand['column']}:**")
            print(f"  - Nulos: {driver_analysis['null_count']:,} ({driver_analysis['null_pct']:.2f}%)")
            print(f"  - Valores distintos: {driver_analysis['distinct_count']:,}")
            print()
    else:
        print("[WARN] No hay columnas de driver_id para analizar")
    print()
    
    # D) Comparación de fechas candidatas
    print("## D) COMPARACIÓN DE FECHAS CANDIDATAS\n")
    if date_candidates:
        print("| Columna | Min | Max | Nulos | % Nulos | Conteo con Status=Completado |")
        print("|---------|-----|-----|-------|---------|------------------------------|")
        
        for cand in date_candidates[:5]:  # Top 5 por prioridad
            date_analysis = analyze_date_field(cursor, cand['column'], total_rows, status_column, completed_value)
            min_str = str(date_analysis['min'])[:19] if date_analysis['min'] else 'N/A'
            max_str = str(date_analysis['max'])[:19] if date_analysis['max'] else 'N/A'
            completed_str = f"{date_analysis['completed_count']:,}" if date_analysis['completed_count'] else 'N/A'
            print(f"| {cand['column']} | {min_str} | {max_str} | {date_analysis['null_count']:,} | {date_analysis['null_pct']:.2f}% | {completed_str} |")
    else:
        print("[WARN] No hay columnas de fecha para analizar")
    print()
    
    # E) Detección de campo monto/ticket
    print("## E) DETECCIÓN DE CAMPO MONTO/TICKET\n")
    if amount_candidates:
        for cand in amount_candidates:
            amount_analysis = analyze_amount_field(cursor, cand['column'], total_rows)
            print(f"**{cand['column']}** ({cand['type']}):\n")
            print(f"- Nulos: {amount_analysis['null_count']:,} ({amount_analysis['null_pct']:.2f}%)")
            if amount_analysis['min'] is not None:
                print(f"- Min: {amount_analysis['min']}")
                print(f"- Max: {amount_analysis['max']}")
                print(f"- P50 (Mediana): {amount_analysis['p50']}")
                print(f"- P95: {amount_analysis['p95']}")
                print(f"- Promedio: {amount_analysis['avg']:.2f}")
            print()
    else:
        print("[WARN] No se encontraron columnas de monto en `public.trips_all`\n")
    print()
    
    # F) Tablas potenciales relacionadas
    print("## F) TABLAS POTENCIALES RELACIONADAS (si no hay monto en trips_all)\n")
    related_tables = []
    if not amount_candidates:
        related_tables = find_related_tables(cursor)
        if related_tables:
            for rel in related_tables:
                print(f"**{rel['schema']}.{rel['table']}:**")
                if rel['amount_columns']:
                    print("  - Columnas de monto:")
                    for col in rel['amount_columns']:
                        print(f"    - `{col['name']}` ({col['type']})")
                if rel['key_columns']:
                    print("  - Columnas clave (posibles FKs):")
                    for col in rel['key_columns']:
                        print(f"    - `{col['name']}` ({col['type']})")
                print()
        else:
            print("[WARN] No se encontraron tablas relacionadas con nombres esperados")
    else:
        print("[INFO] Se encontraron columnas de monto en `trips_all`, no es necesario buscar tablas relacionadas")
    print()
    
    # 2. PROPUESTA DE CONTRATO REAL
    print("## 2. PROPUESTA DE CONTRATO REAL RECOMENDADO\n")
    
    # Determinar valores recomendados
    recommended_status_col = status_candidates[0]['column'] if status_candidates else None
    recommended_status_val = completed_value if completed_value else None
    
    recommended_driver_col = driver_candidates[0]['column'] if driver_candidates else None
    
    recommended_date_col = None
    if date_candidates:
        # Priorizar la que tenga menos nulos y más registros con status completado
        best_date = None
        best_score = -1
        for cand in date_candidates[:5]:
            date_analysis = analyze_date_field(cursor, cand['column'], total_rows, status_column, completed_value)
            # Score: menor % nulos, mayor conteo completado
            score = (100 - date_analysis['null_pct']) * 0.5
            if date_analysis['completed_count']:
                score += min(date_analysis['completed_count'] / total_rows * 100, 50)
            if score > best_score:
                best_score = score
                best_date = cand
        recommended_date_col = best_date['column'] if best_date else date_candidates[0]['column']
    
    recommended_amount_col = amount_candidates[0]['column'] if amount_candidates else None
    
    print("```yaml")
    print("CONTRATO_REAL:")
    print(f"  completed_filter:")
    print(f"    campo: '{recommended_status_col if recommended_status_col else 'NOT_AVAILABLE'}'")
    print(f"    valor: '{recommended_status_val if recommended_status_val else 'NOT_AVAILABLE'}'")
    print(f"  driver_key:")
    print(f"    campo: '{recommended_driver_col if recommended_driver_col else 'NOT_AVAILABLE'}'")
    print(f"  trip_datetime:")
    print(f"    campo: '{recommended_date_col if recommended_date_col else 'NOT_AVAILABLE'}'")
    print(f"  trip_amount:")
    print(f"    campo: '{recommended_amount_col if recommended_amount_col else 'NOT_AVAILABLE'}'")
    print("```\n")
    
    print("### JUSTIFICACIÓN\n")
    
    if recommended_status_col:
        print(f"- **completed_filter**: Se recomienda `{recommended_status_col} = '{recommended_status_val}'` porque:")
        if completed_value:
            cnt = next((cnt for val, cnt in analyze_status_values(cursor, recommended_status_col, total_rows)['values'] 
                       if val == completed_value), 0)
            pct = (cnt / total_rows * 100) if total_rows > 0 else 0
            print(f"  - El valor '{completed_value}' representa {cnt:,} registros ({pct:.2f}% del total)")
        print(f"  - Es la columna de estado más relevante encontrada en la tabla\n")
    else:
        print("- **completed_filter**: [WARN] No se encontró columna de status adecuada. Se requiere investigación adicional.\n")
    
    if recommended_driver_col:
        driver_analysis = analyze_driver_field(cursor, recommended_driver_col, total_rows)
        print(f"- **driver_key**: Se recomienda `{recommended_driver_col}` porque:")
        print(f"  - Tiene {driver_analysis['null_pct']:.2f}% de valores nulos")
        print(f"  - Identifica {driver_analysis['distinct_count']:,} conductores distintos\n")
    else:
        print("- **driver_key**: [WARN] No se encontró columna de driver_id. Se requiere investigación adicional.\n")
    
    if recommended_date_col:
        date_analysis = analyze_date_field(cursor, recommended_date_col, total_rows, status_column, completed_value)
        print(f"- **trip_datetime**: Se recomienda `{recommended_date_col}` porque:")
        print(f"  - Rango de fechas: {date_analysis['min']} a {date_analysis['max']}")
        print(f"  - Tiene {date_analysis['null_pct']:.2f}% de valores nulos")
        if date_analysis['completed_count']:
            print(f"  - {date_analysis['completed_count']:,} registros con status completado tienen fecha válida\n")
        else:
            print(f"  - Es la columna de fecha más relevante encontrada\n")
    else:
        print("- **trip_datetime**: [WARN] No se encontró columna de fecha adecuada. Se requiere investigación adicional.\n")
    
    if recommended_amount_col:
        amount_analysis = analyze_amount_field(cursor, recommended_amount_col, total_rows)
        print(f"- **trip_amount**: Se recomienda `{recommended_amount_col}` porque:")
        print(f"  - Tiene {amount_analysis['null_pct']:.2f}% de valores nulos")
        if amount_analysis['min'] is not None:
            print(f"  - Rango: {amount_analysis['min']} - {amount_analysis['max']}")
            print(f"  - Mediana (P50): {amount_analysis['p50']}")
        print(f"  - Se encuentra directamente en la tabla trips_all\n")
    else:
        print("- **trip_amount**: [WARN] No se encontró columna de monto en `trips_all`.")
        if related_tables:
            print(f"  - Se encontraron {len(related_tables)} tabla(s) relacionada(s) que podrían contener montos:")
            for rel in related_tables[:3]:
                print(f"    - {rel['schema']}.{rel['table']} (columnas de monto: {[c['name'] for c in rel['amount_columns']]})")
        print("  - Se requiere investigación adicional o join con tabla relacionada.\n")
    
    print("="*80)
    print("FIN DEL REPORTE")
    print("="*80 + "\n")

def main():
    """Función principal."""
    try:
        init_db_pool()
        with get_db() as conn:
            cursor = conn.cursor()
            generate_report(cursor)
            cursor.close()
    except Exception as e:
        print(f"\n[ERROR] Error durante la auditoria: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
