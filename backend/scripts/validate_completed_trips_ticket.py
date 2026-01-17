"""
Script de validación del campo canónico de ticket/monto para viajes COMPLETADOS.

OBJETIVO: Validar y recomendar el campo ticket_real más adecuado para registros con condicion = 'Completado'.
"""

import sys
import os
import io

# Configurar codificación UTF-8 para salida
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def safe_execute(cursor, query, description="", params=None):
    """Ejecuta una consulta de forma segura y retorna resultados."""
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchall()
    except Exception as e:
        print(f"  [WARN] Error en {description}: {e}")
        return []

def get_completed_count(cursor):
    """Obtiene el total de registros completados."""
    query = "SELECT COUNT(*) FROM public.trips_all WHERE condicion = 'Completado'"
    result = safe_execute(cursor, query, "contar completados")
    return result[0][0] if result else 0

def analyze_null_percentages(cursor, completed_count):
    """Analiza % nulos de campos de monto en registros completados."""
    fields = [
        'precio_yango_pro', 'efectivo', 'tarjeta', 'pago_corporativo',
        'propina', 'promocion', 'bonificaciones', 'otros_pagos'
    ]
    
    results = {}
    for field in fields:
        query = f"""
            SELECT 
                COUNT(*) FILTER (WHERE {field} IS NULL) as null_count,
                COUNT(*) FILTER (WHERE {field} IS NOT NULL) as not_null_count
            FROM public.trips_all
            WHERE condicion = 'Completado'
        """
        result = safe_execute(cursor, query, f"analizar nulos en {field}")
        if result:
            null_count = result[0][0]
            not_null_count = result[0][1]
            null_pct = (null_count / completed_count * 100) if completed_count > 0 else 0
            results[field] = {
                'null_count': null_count,
                'not_null_count': not_null_count,
                'null_pct': null_pct
            }
    return results

def analyze_ticket_candidate(cursor, ticket_name, ticket_expression, completed_count):
    """Analiza un candidato de ticket."""
    # Crear query con el candidato
    query = f"""
        WITH ticket_calc AS (
            SELECT 
                id,
                codigo_pedido,
                park_id,
                tipo_servicio,
                condicion,
                precio_yango_pro,
                efectivo,
                tarjeta,
                pago_corporativo,
                {ticket_expression} as ticket_value
            FROM public.trips_all
            WHERE condicion = 'Completado'
        )
        SELECT * FROM ticket_calc
    """
    
    # Estadísticas básicas
    stats_query = f"""
        WITH ticket_calc AS (
            SELECT {ticket_expression} as ticket_value
            FROM public.trips_all
            WHERE condicion = 'Completado'
        )
        SELECT 
            COUNT(*) FILTER (WHERE ticket_value IS NULL) as null_count,
            COUNT(*) FILTER (WHERE ticket_value IS NOT NULL) as not_null_count,
            COUNT(*) FILTER (WHERE ticket_value <= 0) as zero_or_negative_count,
            MIN(ticket_value) as min_val,
            MAX(ticket_value) as max_val,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY ticket_value) as p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ticket_value) as p95,
            AVG(ticket_value) as avg_val
        FROM ticket_calc
    """
    
    stats_result = safe_execute(cursor, stats_query, f"estadísticas de {ticket_name}")
    
    stats = {}
    if stats_result and stats_result[0]:
        row = stats_result[0]
        null_count = row[0] if row[0] else 0
        stats = {
            'null_count': null_count,
            'not_null_count': row[1] if row[1] else 0,
            'zero_or_negative_count': row[2] if row[2] else 0,
            'null_pct': (null_count / completed_count * 100) if completed_count > 0 else 0,
            'min': row[3],
            'max': row[4],
            'p50': row[5],
            'p95': row[6],
            'avg': row[7]
        }
    
    # Top 20 outliers (mayores valores)
    outliers_query = f"""
        WITH ticket_calc AS (
            SELECT 
                id,
                codigo_pedido,
                park_id,
                tipo_servicio,
                condicion,
                precio_yango_pro,
                efectivo,
                tarjeta,
                pago_corporativo,
                {ticket_expression} as ticket_value
            FROM public.trips_all
            WHERE condicion = 'Completado'
            AND {ticket_expression} IS NOT NULL
        )
        SELECT 
            id,
            codigo_pedido,
            park_id,
            tipo_servicio,
            condicion,
            precio_yango_pro,
            efectivo,
            tarjeta,
            pago_corporativo,
            ticket_value
        FROM ticket_calc
        ORDER BY ticket_value DESC
        LIMIT 20
    """
    
    outliers_result = safe_execute(cursor, outliers_query, f"outliers de {ticket_name}")
    outliers = []
    if outliers_result:
        for row in outliers_result:
            outliers.append({
                'id': row[0],
                'codigo_pedido': row[1],
                'park_id': row[2],
                'tipo_servicio': row[3],
                'condicion': row[4],
                'precio_yango_pro': row[5],
                'efectivo': row[6],
                'tarjeta': row[7],
                'pago_corporativo': row[8],
                'ticket_value': row[9]
            })
    
    return {
        'stats': stats,
        'outliers': outliers
    }

def generate_report(cursor):
    """Genera el reporte completo de validación."""
    print("\n" + "="*80)
    print("VALIDACIÓN DE TICKET/MONTO PARA VIAJES COMPLETADOS")
    print("="*80 + "\n")
    
    print("**Reglas Fijas:**\n")
    print("- completed_filter: `condicion = 'Completado'`\n")
    
    # Obtener conteo de completados
    completed_count = get_completed_count(cursor)
    print(f"**Total de registros completados:** {completed_count:,}\n")
    
    # 1) Análisis de % nulos en campos individuales
    print("## 1) ANÁLISIS DE % NULOS EN CAMPOS DE MONTO (COMPLETADOS)\n")
    print("| Campo | Nulos | No Nulos | % Nulos |")
    print("|-------|-------|----------|---------|")
    
    null_analysis = analyze_null_percentages(cursor, completed_count)
    for field, data in null_analysis.items():
        print(f"| `{field}` | {data['null_count']:,} | {data['not_null_count']:,} | {data['null_pct']:.2f}% |")
    print()
    
    # 2) Análisis de candidatos de ticket
    print("## 2) ANÁLISIS DE TICKETS CANDIDATOS\n")
    
    # Definir candidatos
    candidates = {
        't1': "precio_yango_pro",
        't2': "COALESCE(precio_yango_pro, COALESCE(efectivo,0)+COALESCE(tarjeta,0)+COALESCE(pago_corporativo,0))",
        't3': "COALESCE(efectivo,0)+COALESCE(tarjeta,0)+COALESCE(pago_corporativo,0)"
    }
    
    candidate_results = {}
    
    for ticket_name, ticket_expr in candidates.items():
        print(f"### {ticket_name.upper()}: {ticket_expr}\n")
        
        result = analyze_ticket_candidate(cursor, ticket_name, ticket_expr, completed_count)
        candidate_results[ticket_name] = result
        stats = result['stats']
        
        # Estadísticas generales
        print("**Estadísticas:**\n")
        print("| Métrica | Valor |")
        print("|---------|-------|")
        print(f"| % Nulos | {stats.get('null_pct', 0):.2f}% |")
        min_val = stats.get('min', None)
        min_str = f"{min_val:.2f}" if min_val is not None else 'N/A'
        p50_val = stats.get('p50', None)
        p50_str = f"{p50_val:.2f}" if p50_val is not None else 'N/A'
        p95_val = stats.get('p95', None)
        p95_str = f"{p95_val:.2f}" if p95_val is not None else 'N/A'
        max_val = stats.get('max', None)
        max_str = f"{max_val:.2f}" if max_val is not None else 'N/A'
        print(f"| Min | {min_str} |")
        print(f"| P50 (Mediana) | {p50_str} |")
        print(f"| P95 | {p95_str} |")
        print(f"| Max | {max_str} |")
        avg_val = stats.get('avg', None)
        avg_str = f"{avg_val:.2f}" if avg_val is not None else 'N/A'
        print(f"| Promedio | {avg_str} |")
        print(f"| Valores <= 0 | {stats.get('zero_or_negative_count', 0):,} |")
        print()
        
        # Top 20 outliers
        print(f"**Top 20 Outliers (Mayores Valores):**\n")
        if result['outliers']:
            print("| ID | Código Pedido | Park ID | Tipo Servicio | Precio Yango Pro | Efectivo | Tarjeta | Pago Corp | Ticket |")
            print("|----|---------------|---------|---------------|------------------|----------|---------|-----------|--------|")
            
            for outlier in result['outliers']:
                id_val = str(outlier['id'])[:20] if outlier['id'] else 'N/A'
                codigo = str(outlier['codigo_pedido'])[:20] if outlier['codigo_pedido'] else 'N/A'
                park = str(outlier['park_id'])[:15] if outlier['park_id'] else 'N/A'
                tipo = str(outlier['tipo_servicio'])[:20] if outlier['tipo_servicio'] else 'N/A'
                precio = f"{outlier['precio_yango_pro']:.2f}" if outlier['precio_yango_pro'] is not None else 'NULL'
                efectivo = f"{outlier['efectivo']:.2f}" if outlier['efectivo'] is not None else 'NULL'
                tarjeta = f"{outlier['tarjeta']:.2f}" if outlier['tarjeta'] is not None else 'NULL'
                corp = f"{outlier['pago_corporativo']:.2f}" if outlier['pago_corporativo'] is not None else 'NULL'
                ticket = f"{outlier['ticket_value']:.2f}" if outlier['ticket_value'] is not None else 'NULL'
                
                print(f"| {id_val} | {codigo} | {park} | {tipo} | {precio} | {efectivo} | {tarjeta} | {corp} | {ticket} |")
        else:
            print("No se encontraron outliers.")
        print()
    
    # 3) Recomendación final
    print("## 3) RECOMENDACIÓN FINAL\n")
    
    # Comparar candidatos
    print("**Comparación de Candidatos:**\n")
    print("| Candidato | % Nulos | P50 | P95 | Max | Valores <= 0 |")
    print("|-----------|---------|-----|-----|-----|--------------|")
    
    for ticket_name in ['t1', 't2', 't3']:
        stats = candidate_results[ticket_name]['stats']
        null_pct = stats.get('null_pct', 0)
        p50 = stats.get('p50', 0)
        p95 = stats.get('p95', 0)
        max_val = stats.get('max', 0)
        zeros = stats.get('zero_or_negative_count', 0)
        
        p50_str = f"{p50:.2f}" if p50 is not None else 'N/A'
        p95_str = f"{p95:.2f}" if p95 is not None else 'N/A'
        max_str = f"{max_val:.2f}" if max_val is not None else 'N/A'
        
        print(f"| {ticket_name} | {null_pct:.2f}% | {p50_str} | {p95_str} | {max_str} | {zeros:,} |")
    print()
    
    # Decidir recomendación
    # Priorizar: menor % nulos, outliers razonables
    t1_stats = candidate_results['t1']['stats']
    t2_stats = candidate_results['t2']['stats']
    t3_stats = candidate_results['t3']['stats']
    
    t1_null_pct = t1_stats.get('null_pct', 100)
    t2_null_pct = t2_stats.get('null_pct', 100)
    t3_null_pct = t3_stats.get('null_pct', 100)
    
    # Verificar outliers extremos
    t1_max = t1_stats.get('max', 0) or 0
    t2_max = t2_stats.get('max', 0) or 0
    t3_max = t3_stats.get('max', 0) or 0
    
    # Decisión: menor % nulos, pero verificar consistencia
    # Si cobertura es similar, priorizar simplicidad y consistencia
    recommended = 't1'
    justification_points = []
    
    t1_zeros = t1_stats.get('zero_or_negative_count', 0)
    t2_zeros = t2_stats.get('zero_or_negative_count', 0)
    t3_zeros = t3_stats.get('zero_or_negative_count', 0)
    
    # Si todos tienen cobertura similar (diferencia < 1%), priorizar simplicidad y consistencia
    if abs(t2_null_pct - t1_null_pct) < 1 and abs(t3_null_pct - t1_null_pct) < 1:
        # Todos tienen similar cobertura, priorizar por simplicidad y consistencia
        if t1_zeros <= t2_zeros and t1_zeros <= t3_zeros:
            recommended = 't1'
            justification_points.append(f"t1 es el más simple (campo directo) y tiene {t1_zeros} registros con valores <= 0")
        elif t2_zeros < t1_zeros and t2_zeros <= t3_zeros:
            recommended = 't2'
            justification_points.append(f"t2 tiene mejor consistencia ({t2_zeros} valores <= 0 vs {t1_zeros} de t1)")
        else:
            recommended = 't3'
            justification_points.append(f"t3 tiene mejor consistencia ({t3_zeros} valores <= 0 vs {t1_zeros} de t1), aunque es más complejo")
    elif t2_null_pct < t1_null_pct:
        recommended = 't2'
        justification_points.append(f"t2 tiene mejor cobertura ({t2_null_pct:.2f}% nulos vs {t1_null_pct:.2f}% de t1)")
    elif t3_null_pct < t1_null_pct:
        # Solo recomendar t3 si tiene mucho mejor cobertura
        if t3_null_pct < t1_null_pct - 5:  # Al menos 5% mejor
            recommended = 't3'
            justification_points.append(f"t3 tiene mejor cobertura ({t3_null_pct:.2f}% nulos vs {t1_null_pct:.2f}% de t1)")
        else:
            recommended = 't1'
            justification_points.append(f"t1 es preferible sobre t3 por menor complejidad, aunque t3 tiene mejor cobertura")
    else:
        recommended = 't1'
        justification_points.append(f"t1 tiene la mejor cobertura ({t1_null_pct:.2f}% nulos) y es el más simple")
    
    # Verificar consistencia (outliers extremos)
    recommended_stats = candidate_results[recommended]['stats']
    recommended_max = recommended_stats.get('max', 0) or 0
    
    if recommended_max > 100000:  # Valores muy altos
        justification_points.append(f"⚠️ Atención: t{recommended[-1]} tiene outliers muy altos (max: {recommended_max:.2f}), revisar top 20 outliers arriba")
    
    # Valores <= 0
    zeros = recommended_stats.get('zero_or_negative_count', 0)
    if zeros > 0:
        zeros_pct = (zeros / completed_count * 100) if completed_count > 0 else 0
        justification_points.append(f"t{recommended[-1]} tiene {zeros:,} registros con valores <= 0 ({zeros_pct:.2f}% del total)")
    
    print("**TICKET_REAL_CONGELADO:**\n")
    print("```yaml")
    print("TICKET_REAL:")
    print(f"  ticket_field: '{recommended}'")
    print(f"  ticket_expression: '{candidates[recommended]}'")
    print(f"  null_percentage: {recommended_stats.get('null_pct', 0):.2f}%")
    print("```\n")
    
    print("**Justificación:**\n")
    for point in justification_points:
        print(f"- {point}")
    print()
    
    # Detalles adicionales
    print("**Detalles del Ticket Recomendado:**\n")
    print(f"- **Campo/Expresión:** `{candidates[recommended]}`")
    print(f"- **% Nulos:** {recommended_stats.get('null_pct', 0):.2f}%")
    print(f"- **Cobertura:** {(100 - recommended_stats.get('null_pct', 0)):.2f}% de registros completados tienen valor")
    print(f"- **Rango:** {recommended_stats.get('min', 'N/A')} - {recommended_stats.get('max', 'N/A')}")
    print(f"- **Mediana (P50):** {recommended_stats.get('p50', 'N/A')}")
    print(f"- **P95:** {recommended_stats.get('p95', 'N/A')}")
    print(f"- **Registros con valor <= 0:** {recommended_stats.get('zero_or_negative_count', 0):,}")
    print()
    
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
        print(f"\n[ERROR] Error durante la validación: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
