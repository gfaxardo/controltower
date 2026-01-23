"""
Script de diagnóstico para encontrar dónde están las LOB del plan.
Inspecciona el schema 'plan' (y otros schemas relevantes) buscando tablas
que contengan columnas relacionadas con LOB.

Genera un reporte en markdown con:
- Tablas candidatas
- Columnas relevantes encontradas
- Conteo de filas
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose_plan_lob_source():
    """
    Diagnostica dónde están las LOB del plan.
    """
    init_db_pool()
    
    report_lines = []
    report_lines.append("# Diagnóstico: Fuentes de LOB del Plan\n")
    report_lines.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            # 1. Buscar tablas en schemas relevantes
            schemas_to_check = ['plan', 'canon', 'ops']
            report_lines.append("## 1. Tablas Candidatas\n\n")
            
            all_candidates = []
            
            for schema in schemas_to_check:
                try:
                    cursor.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                        ORDER BY table_name
                    """, (schema,))
                    
                    tables = cursor.fetchall()
                except Exception as e:
                    logger.warning(f"Error al buscar tablas en schema {schema}: {e}")
                    tables = []
                
                if tables:
                    report_lines.append(f"### Schema: `{schema}`\n\n")
                    
                    for table_row in tables:
                        table_name = table_row[0] if isinstance(table_row, tuple) else table_row
                        
                        # Buscar columnas relacionadas con LOB
                        try:
                            cursor.execute("""
                                SELECT column_name, data_type
                                FROM information_schema.columns
                                WHERE table_schema = %s
                                AND table_name = %s
                                AND (
                                    column_name ILIKE '%lob%'
                                    OR column_name ILIKE '%line_of_business%'
                                    OR column_name ILIKE '%tipo_servicio%'
                                    OR column_name ILIKE '%service_type%'
                                    OR column_name ILIKE '%business_line%'
                                    OR column_name ILIKE '%segment%'
                                    OR column_name ILIKE '%vertical%'
                                )
                                ORDER BY column_name
                            """, (schema, table_name))
                            
                            lob_columns = cursor.fetchall()
                        except Exception as e:
                            # Solo loggear si es un error real, no si simplemente no hay columnas LOB
                            logger.debug(f"Error al buscar columnas LOB en {schema}.{table_name}: {e}")
                            lob_columns = []
                        
                        if lob_columns:
                            # Contar filas
                            try:
                                cursor.execute(f"SELECT COUNT(*) FROM {schema}.{table_name}")
                                result = cursor.fetchone()
                                row_count = result[0] if result else None
                            except Exception as e:
                                logger.warning(f"Error al contar filas en {schema}.{table_name}: {e}")
                                row_count = None
                            
                            # Obtener todas las columnas para contexto
                            cursor.execute("""
                                SELECT column_name, data_type
                                FROM information_schema.columns
                                WHERE table_schema = %s
                                AND table_name = %s
                                ORDER BY ordinal_position
                            """, (schema, table_name))
                            
                            all_columns = cursor.fetchall()
                            
                            candidate = {
                                'schema': schema,
                                'table': table_name,
                                'lob_columns': lob_columns,
                                'all_columns': all_columns,
                                'row_count': row_count
                            }
                            all_candidates.append(candidate)
                            
                            report_lines.append(f"#### Tabla: `{schema}.{table_name}`\n")
                            report_lines.append(f"- **Filas**: {row_count if row_count is not None else 'N/A'}\n")
                            report_lines.append(f"- **Columnas LOB encontradas**:\n")
                            for col_name, col_type in lob_columns:
                                report_lines.append(f"  - `{col_name}` ({col_type})\n")
                            
                            # Columnas relevantes adicionales
                            relevant_cols = ['country', 'city', 'period', 'year', 'month']
                            found_relevant = []
                            for col_name, col_type in all_columns:
                                if any(rel in col_name.lower() for rel in relevant_cols):
                                    found_relevant.append((col_name, col_type))
                            
                            if found_relevant:
                                report_lines.append(f"- **Columnas relevantes adicionales**:\n")
                                for col_name, col_type in found_relevant:
                                    report_lines.append(f"  - `{col_name}` ({col_type})\n")
                            
                            report_lines.append("\n")
            
            if not all_candidates:
                report_lines.append("⚠️ **No se encontraron tablas candidatas con columnas de LOB.**\n\n")
            else:
                report_lines.append(f"**Total de tablas candidatas encontradas**: {len(all_candidates)}\n\n")
            
            # 2. Inspeccionar trips_all
            report_lines.append("## 2. Estructura de trips_all\n\n")
            
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'trips_all'
                ORDER BY ordinal_position
            """)
            
            trips_columns = cursor.fetchall()
            
            report_lines.append(f"**Total de columnas**: {len(trips_columns)}\n\n")
            report_lines.append("### Columnas relevantes para LOB:\n\n")
            
            relevant_trips_cols = []
            for col_row in trips_columns:
                if len(col_row) >= 3:
                    col_name, col_type, is_nullable = col_row[0], col_row[1], col_row[2]
                elif len(col_row) >= 2:
                    col_name, col_type = col_row[0], col_row[1]
                    is_nullable = 'YES'
                else:
                    continue
                    
                col_lower = col_name.lower()
                if any(term in col_lower for term in ['tipo_servicio', 'service_type', 'pago_corporativo', 'corporate', 'country', 'city', 'id', 'fecha', 'date', 'trip']):
                    relevant_trips_cols.append((col_name, col_type, is_nullable))
                    report_lines.append(f"- `{col_name}` ({col_type}, nullable: {is_nullable})\n")
            
            if not relevant_trips_cols:
                report_lines.append("⚠️ No se encontraron columnas relevantes obvias.\n")
            
            # 3. Recomendaciones
            report_lines.append("\n## 3. Recomendaciones\n\n")
            
            if all_candidates:
                best_candidate = None
                for cand in all_candidates:
                    # Priorizar tablas con más filas y columnas LOB claras
                    if cand['row_count'] and cand['row_count'] > 0:
                        if not best_candidate or cand['row_count'] > best_candidate.get('row_count', 0):
                            best_candidate = cand
                
                if best_candidate:
                    report_lines.append(f"✅ **Tabla recomendada**: `{best_candidate['schema']}.{best_candidate['table']}`\n")
                    report_lines.append(f"   - Filas: {best_candidate['row_count']}\n")
                    report_lines.append(f"   - Columnas LOB: {[c[0] for c in best_candidate['lob_columns']]}\n\n")
            else:
                report_lines.append("⚠️ **No se encontraron tablas con LOB del plan.**\n")
                report_lines.append("   El sistema funcionará en modo REAL-only hasta que se cargue el plan.\n\n")
            
            # Guardar reporte
            report_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'PLAN_LOB_SOURCE_DIAGNOSIS.md'
            )
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.writelines(report_lines)
            
            logger.info(f"✅ Reporte generado: {report_path}")
            
            # Mostrar resumen en consola
            print("\n" + "=" * 60)
            print("RESUMEN DEL DIAGNÓSTICO")
            print("=" * 60)
            print(f"Tablas candidatas encontradas: {len(all_candidates)}")
            if all_candidates:
                for cand in all_candidates:
                    print(f"  - {cand['schema']}.{cand['table']}: {cand['row_count']} filas")
            print(f"\nReporte completo guardado en: {report_path}")
            print("=" * 60)
            
        except Exception as e:
            logger.error(f"Error en diagnóstico: {e}")
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    diagnose_plan_lob_source()
