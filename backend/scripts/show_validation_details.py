"""Script para mostrar top 20 validaciones."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import init_db_pool, get_db

plan_version = sys.argv[1] if len(sys.argv) > 1 else 'ruta27_v2026_01_16_a'
init_db_pool()
with get_db() as conn:
    cursor = conn.cursor()
    
    # Top 20 validaciones
    cursor.execute("""
        SELECT 
            validation_type,
            severity,
            country,
            city,
            lob_base,
            segment,
            month,
            row_count
        FROM ops.plan_validation_results
        WHERE plan_version = %s
        ORDER BY 
            CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
            row_count DESC
        LIMIT 20
    """, (plan_version,))
    
    print(f"\nTop 20 Validaciones para {plan_version}:")
    print("="*100)
    print("| Tipo | Severidad | Country | City | LOB | Segment | Month | Count |")
    print("|------|-----------|---------|------|-----|---------|-------|-------|")
    
    for row in cursor.fetchall():
        print(f"| {row[0]} | {row[1]} | {row[2] or 'NULL'} | {row[3] or 'NULL'} | {row[4] or 'NULL'} | {row[5] or 'NULL'} | {row[6]} | {row[7]} |")
    
    # Conteos por tipo y severidad
    cursor.execute("""
        SELECT 
            validation_type,
            severity,
            COUNT(*) as count,
            SUM(row_count) as total_rows
        FROM ops.plan_validation_results
        WHERE plan_version = %s
        GROUP BY validation_type, severity
        ORDER BY 
            CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
            validation_type
    """, (plan_version,))
    
    print("\n" + "="*100)
    print("Conteos por validation_type y severity:")
    print("| Tipo | Severidad | Cantidad | Total Filas |")
    print("|------|-----------|----------|-------------|")
    
    for row in cursor.fetchall():
        print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]:,} |")
    
    cursor.close()
