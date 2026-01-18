"""
AUDITORÃA END-TO-END: Revenue Plan Bug (GMV Inferido)
Tech Lead de Datos - YEGO Control Tower

Ejecuta paso a paso la auditorÃ­a y correcciÃ³n del bug de Revenue Plan.
"""

import sys
import os

# Agregar el directorio backend al path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def execute_query(query, description=""):
    """Ejecuta una query y retorna resultados."""
    try:
        init_db_pool()  # Inicializar pool si no estÃ¡ inicializado
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in results]
    except Exception as e:
        print(f"[ERROR] ERROR en {description}: {e}")
        import traceback
        traceback.print_exc()
        return None

def execute_command(query, description=""):
    """Ejecuta un comando (CREATE, DROP, etc.) sin retornar resultados."""
    try:
        init_db_pool()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            cursor.close()
            print(f"[OK] {description}")
            return True
    except Exception as e:
        print(f"[ERROR] ERROR en {description}: {e}")
        import traceback
        traceback.print_exc()
        return False

# Inicializar el pool al inicio
init_db_pool()

print("=" * 70)
print("PASO 1 â€” DESCUBRIR TABLAS DE PLAN (RAW / STAGING)")
print("=" * 70)

query1 = """
SELECT
  table_schema,
  table_name
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog','information_schema')
  AND (
    table_name ILIKE '%plan%'
    OR table_name ILIKE '%projection%'
    OR table_name ILIKE '%ruta%'
    OR table_name ILIKE '%upload%'
  )
ORDER BY table_schema, table_name;
"""

results1 = execute_query(query1, "Paso 1: Buscar tablas de Plan")
if not results1:
    print("[ERROR] No se pudieron obtener las tablas")
    sys.exit(1)

print("\n[TABLAS ENCONTRADAS]:")
for row in results1:
    print(f"  - {row['table_schema']}.{row['table_name']}")

# Identificar tabla RAW (generalmente la que tiene mÃ¡s filas y granularidad detallada)
print("\n[BUSCANDO TABLA RAW DEL PLAN]...")
plan_raw_table = None
plan_raw_schema = None

# Buscar en schema 'plan' o 'ops' con nombres especÃ­ficos
for row in results1:
    schema = row['table_schema']
    table = row['table_name']
    
    # Posibles nombres de tablas RAW
    if table in ['plan_long_raw', 'plan_long_valid', 'stg_plan_trips_monthly'] or \
       (schema == 'plan' and 'raw' in table.lower()) or \
       (schema == 'ops' and 'plan_trips_monthly' in table.lower()):
        plan_raw_table = table
        plan_raw_schema = schema
        break

# Si no se encontrÃ³, usar la primera tabla que tenga estructura de plan
if not plan_raw_table:
    # Buscar tabla con columnas tÃ­picas de plan
    for row in results1:
        schema = row['table_schema']
        table = row['table_name']
        query_check = f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = '{schema}' AND table_name = '{table}'
        AND column_name IN ('trips_plan', 'revenue_plan', 'year', 'month', 'country')
        LIMIT 1;
        """
        check_result = execute_query(query_check)
        if check_result:
            plan_raw_table = table
            plan_raw_schema = schema
            break

if not plan_raw_table:
    print("[ERROR] No se pudo identificar la tabla RAW del Plan")
    print("Usando ops.plan_trips_monthly como fallback")
    plan_raw_table = 'plan_trips_monthly'
    plan_raw_schema = 'ops'

print(f"\n[OK] Tabla RAW identificada: {plan_raw_schema}.{plan_raw_table}")

print("\n" + "=" * 70)
print("PASO 2 â€” VERIFICAR SI EXISTE revenue_plan")
print("=" * 70)

query2 = f"""
SELECT
  column_name,
  data_type
FROM information_schema.columns
WHERE table_schema = '{plan_raw_schema}'
  AND table_name = '{plan_raw_table}'
ORDER BY ordinal_position;
"""

results2 = execute_query(query2, "Paso 2: Verificar columnas")
if not results2:
    print("[ERROR] No se pudieron obtener las columnas")
    sys.exit(1)

print("\n[COLUMNAS ENCONTRADAS]:")
has_revenue_plan = False
has_avg_ticket = False
has_trips_plan = False

for row in results2:
    col_name = row['column_name']
    col_type = row['data_type']
    print(f"  - {col_name} ({col_type})")
    
    if 'revenue_plan' in col_name.lower() or 'projected_revenue' in col_name.lower():
        has_revenue_plan = True
    if 'avg_ticket' in col_name.lower() or 'ticket' in col_name.lower():
        has_avg_ticket = True
    if 'trips_plan' in col_name.lower() or 'projected_trips' in col_name.lower():
        has_trips_plan = True

print(f"\n[VERIFICACION]:")
print(f"  - revenue_plan existe: {'[SI]' if has_revenue_plan else '[NO]'}")
print(f"  - avg_ticket existe: {'[SI]' if has_avg_ticket else '[NO]'}")
print(f"  - trips_plan existe: {'[SI]' if has_trips_plan else '[NO]'}")

if not has_revenue_plan:
    print("\n[ERROR] INGESTA INCORRECTA: revenue_plan no se persiste en la tabla RAW")
    print("[WARN]  El archivo no estÃ¡ guardando revenue_plan o usa otro nombre de columna")
    sys.exit(1)

print("\n" + "=" * 70)
print("PASO 3 â€” PRUEBA DE FUEGO (DESDE EL ARCHIVO)")
print("=" * 70)

# Adaptar query segÃºn las columnas reales
revenue_col = None
trips_col = None
ticket_col = None

for row in results2:
    col = row['column_name'].lower()
    if 'revenue_plan' in col or 'revenue' in col:
        revenue_col = row['column_name']
    if 'trips_plan' in col or 'projected_trips' in col:
        trips_col = row['column_name']
    if 'avg_ticket' in col or 'ticket' in col or 'projected_ticket' in col:
        ticket_col = row['column_name']

# Ajustar segÃºn schema (algunos usan year/month, otros month DATE)
year_month_cond = ""
if any('year' in r['column_name'].lower() for r in results2):
    year_month_cond = "year = 2026 AND month = 1"
else:
    year_month_cond = "EXTRACT(YEAR FROM month) = 2026 AND EXTRACT(MONTH FROM month) = 1"

query3 = f"""
SELECT
  country,
  SUM({revenue_col})               AS revenue_from_file,
  SUM({trips_col} * {ticket_col})    AS gmv_inferred
FROM {plan_raw_schema}.{plan_raw_table}
WHERE {year_month_cond}
  AND country = 'PE'
GROUP BY country;
"""

results3 = execute_query(query3, "Paso 3: Prueba de fuego")
if results3:
    for row in results3:
        revenue = float(row['revenue_from_file']) if row['revenue_from_file'] else 0
        gmv = float(row['gmv_inferred']) if row['gmv_inferred'] else 0
        print(f"\n Resultados:")
        print(f"  - revenue_from_file: {revenue:,.2f}")
        print(f"  - gmv_inferred: {gmv:,.2f}")
        
        expected_revenue = 263428.97
        if abs(revenue - expected_revenue) < 1000:
            print(f"  [OK] revenue_from_file â‰ˆ {expected_revenue} (CORRECTO)")
        else:
            print(f"  [WARN]  revenue_from_file â‰  {expected_revenue} (revisar)")
        
        if gmv > 8000000:
            print(f"  [OK] gmv_inferred â‰ˆ 8,400,000+ (CORRECTO - muestra que son diferentes)")
        else:
            print(f"  [WARN]  gmv_inferred < 8M (revisar)")
else:
    print("[WARN]  No se encontraron datos para validar. Continuando...")

print("\n" + "=" * 70)
print("PASO 4 â€” IDENTIFICAR LA VISTA QUE CONSUME LA UI")
print("=" * 70)

query4 = """
SELECT
  table_schema,
  table_name
FROM information_schema.views
WHERE (
    table_name ILIKE '%plan%'
    OR table_name ILIKE '%projection%'
  )
  AND (
    table_name ILIKE '%latest%'
    OR table_name ILIKE '%monthly%'
  )
ORDER BY table_schema, table_name;
"""

results4 = execute_query(query4, "Paso 4: Buscar vistas")
if not results4:
    print("[ERROR] No se encontraron vistas")
    sys.exit(1)

print("\n Vistas encontradas:")
for row in results4:
    print(f"  - {row['table_schema']}.{row['table_name']}")

# Identificar vista latest (generalmente ops.v_plan_trips_monthly_latest)
plan_view = None
plan_view_schema = None

for row in results4:
    schema = row['table_schema']
    view = row['table_name']
    if 'latest' in view.lower() and 'monthly' in view.lower():
        plan_view = view
        plan_view_schema = schema
        break

if not plan_view:
    # Fallback a la primera vista monthly
    plan_view = results4[0]['table_name']
    plan_view_schema = results4[0]['table_schema']

print(f"\n[OK] Vista identificada: {plan_view_schema}.{plan_view}")

print("\n" + "=" * 70)
print("PASO 5 â€” INSPECCIONAR DEFINICIÃ“N DE LA VISTA (BUG)")
print("=" * 70)

query5 = f"SELECT pg_get_viewdef('{plan_view_schema}.{plan_view}', true) as view_definition;"

results5 = execute_query(query5, "Paso 5: Obtener definiciÃ³n de vista")
if results5:
    view_def = results5[0]['view_definition']
    print("\n DefiniciÃ³n de la vista:")
    print(view_def[:500] + "..." if len(view_def) > 500 else view_def)
    
    # Buscar el bug
    has_bug_trips_ticket = 'trips' in view_def.lower() and 'ticket' in view_def.lower() and 'revenue' in view_def.lower()
    has_bug_sum = 'sum(trips' in view_def.lower() and 'ticket' in view_def.lower() and 'revenue' in view_def.lower()
    
    if has_bug_trips_ticket or has_bug_sum:
        print("\n[ERROR] BUG CONFIRMADO: La vista calcula revenue como trips Ã— ticket (GMV)")
    else:
        print("\n[OK] La vista NO calcula revenue directamente desde trips Ã— ticket")
else:
    print("[WARN]  No se pudo obtener la definiciÃ³n")

print("\n" + "=" * 70)
print("PASO 6 â€” FIX DEFINITIVO")
print("=" * 70)
print("[WARN]  NOTA: Este paso requiere ajuste manual segÃºn la estructura real de la tabla")
print("    Ejecutando query de validaciÃ³n primero...")

print("\n" + "=" * 70)
print("PASO 7 â€” VALIDACIÃ“N FINAL")
print("=" * 70)

# Primero validar con la vista actual
query7_before = f"""
SELECT
  country,
  SUM(projected_revenue) AS revenue_from_view
FROM {plan_view_schema}.{plan_view}
WHERE EXTRACT(YEAR FROM month) = 2026
  AND EXTRACT(MONTH FROM month) = 1
  AND country = 'PE'
GROUP BY country;
"""

results7_before = execute_query(query7_before, "Paso 7: ValidaciÃ³n antes del fix")
if results7_before:
    print("\n Revenue desde vista (ANTES DEL FIX):")
    for row in results7_before:
        revenue = float(row['revenue_from_view']) if row['revenue_from_view'] else 0
        print(f"  - revenue_from_view: {revenue:,.2f}")
        expected = 263428.97
        if abs(revenue - expected) < 1000:
            print(f"  [OK] CORRECTO (â‰ˆ {expected})")
        else:
            print(f"  [ERROR] INCORRECTO (esperado â‰ˆ {expected})")

print("\n" + "=" * 70)
print("RESUMEN DE AUDITORÃA")
print("=" * 70)
print(f"Tabla RAW: {plan_raw_schema}.{plan_raw_table}")
print(f"Vista: {plan_view_schema}.{plan_view}")
print(f"revenue_plan existe en RAW: {'[OK] SÃ' if has_revenue_plan else '[ERROR] NO'}")
print("\n[WARN]  Para aplicar el fix definitivo, ejecutar:")
print(f"   CREATE OR REPLACE VIEW {plan_view_schema}.{plan_view} AS ...")
print("   (Ver migraciÃ³n 009_fix_revenue_plan_input.py para el fix completo)")


