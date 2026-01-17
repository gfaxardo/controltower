"""Script de smoke test para vistas Plan vs Real (PASO C)."""
import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def smoke_test_views():
    """Ejecuta smoke tests en las vistas Plan vs Real."""
    init_db_pool()
    
    results = {
        'passed': [],
        'failed': [],
        'warnings': []
    }
    
    print("=" * 80)
    print("SMOKE TEST: Vistas Plan vs Real (PASO C)")
    print("=" * 80)
    print()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            # Test 1: Verificar que existe ops.v_real_trips_monthly_latest
            print("[1/8] Verificando ops.v_real_trips_monthly_latest...")
            try:
                cursor.execute("SELECT COUNT(*) FROM ops.v_real_trips_monthly_latest")
                count = cursor.fetchone()[0]
                if count > 0:
                    results['passed'].append("✓ ops.v_real_trips_monthly_latest existe y tiene datos")
                    print(f"  ✓ ops.v_real_trips_monthly_latest: {count:,} registros")
                else:
                    results['warnings'].append("⚠ ops.v_real_trips_monthly_latest existe pero no tiene datos")
                    print(f"  ⚠ ops.v_real_trips_monthly_latest: {count} registros (vacío)")
            except Exception as e:
                results['failed'].append(f"❌ ops.v_real_trips_monthly_latest: {str(e)}")
                print(f"  ✗ Error: {e}")
            
            # Test 2: Verificar que existe ops.v_real_kpis_monthly
            print("[2/8] Verificando ops.v_real_kpis_monthly...")
            try:
                cursor.execute("SELECT COUNT(*) FROM ops.v_real_kpis_monthly")
                count = cursor.fetchone()[0]
                if count > 0:
                    results['passed'].append("✓ ops.v_real_kpis_monthly existe y tiene datos")
                    print(f"  ✓ ops.v_real_kpis_monthly: {count:,} registros")
                else:
                    results['warnings'].append("⚠ ops.v_real_kpis_monthly existe pero no tiene datos")
                    print(f"  ⚠ ops.v_real_kpis_monthly: {count} registros (vacío)")
            except Exception as e:
                results['failed'].append(f"❌ ops.v_real_kpis_monthly: {str(e)}")
                print(f"  ✗ Error: {e}")
            
            # Test 3: Verificar que existe ops.v_plan_vs_real_monthly_latest
            print("[3/8] Verificando ops.v_plan_vs_real_monthly_latest...")
            try:
                cursor.execute("SELECT COUNT(*) FROM ops.v_plan_vs_real_monthly_latest")
                count = cursor.fetchone()[0]
                if count > 0:
                    results['passed'].append("✓ ops.v_plan_vs_real_monthly_latest existe y tiene datos")
                    print(f"  ✓ ops.v_plan_vs_real_monthly_latest: {count:,} registros")
                else:
                    results['warnings'].append("⚠ ops.v_plan_vs_real_monthly_latest existe pero no tiene datos")
                    print(f"  ⚠ ops.v_plan_vs_real_monthly_latest: {count} registros (vacío)")
            except Exception as e:
                results['failed'].append(f"❌ ops.v_plan_vs_real_monthly_latest: {str(e)}")
                print(f"  ✗ Error: {e}")
            
            # Test 4: Verificar que existe ops.v_plan_vs_real_alerts_monthly_latest
            print("[4/8] Verificando ops.v_plan_vs_real_alerts_monthly_latest...")
            try:
                cursor.execute("SELECT COUNT(*) FROM ops.v_plan_vs_real_alerts_monthly_latest")
                count = cursor.fetchone()[0]
                if count > 0:
                    results['passed'].append("✓ ops.v_plan_vs_real_alerts_monthly_latest existe y tiene datos")
                    print(f"  ✓ ops.v_plan_vs_real_alerts_monthly_latest: {count:,} registros")
                else:
                    results['warnings'].append("⚠ ops.v_plan_vs_real_alerts_monthly_latest existe pero no tiene datos")
                    print(f"  ⚠ ops.v_plan_vs_real_alerts_monthly_latest: {count} registros (vacío)")
            except Exception as e:
                results['failed'].append(f"❌ ops.v_plan_vs_real_alerts_monthly_latest: {str(e)}")
                print(f"  ✗ Error: {e}")
            
            # Test 5: Verificar estructura de v_plan_vs_real_monthly_latest
            print("[5/8] Verificando estructura de v_plan_vs_real_monthly_latest...")
            try:
                cursor.execute("""
                    SELECT * FROM ops.v_plan_vs_real_monthly_latest LIMIT 1
                """)
                columns = [desc[0] for desc in cursor.description]
                required_columns = [
                    'country', 'month', 'city_norm_real', 'lob_base', 'segment',
                    'plan_version', 'projected_trips', 'trips_real_completed',
                    'gap_trips', 'gap_revenue_proxy', 'has_plan', 'has_real', 'status_bucket'
                ]
                missing = [col for col in required_columns if col not in columns]
                if not missing:
                    results['passed'].append("✓ v_plan_vs_real_monthly_latest tiene todas las columnas requeridas")
                    print(f"  ✓ Columnas requeridas presentes ({len(required_columns)}/{len(required_columns)})")
                else:
                    results['failed'].append(f"❌ v_plan_vs_real_monthly_latest faltan columnas: {missing}")
                    print(f"  ✗ Faltan columnas: {missing}")
            except Exception as e:
                results['failed'].append(f"❌ Error verificando estructura: {str(e)}")
                print(f"  ✗ Error: {e}")
            
            # Test 6: Verificar estructura de v_plan_vs_real_alerts_monthly_latest
            print("[6/8] Verificando estructura de v_plan_vs_real_alerts_monthly_latest...")
            try:
                cursor.execute("""
                    SELECT * FROM ops.v_plan_vs_real_alerts_monthly_latest LIMIT 1
                """)
                columns = [desc[0] for desc in cursor.description]
                required_columns = [
                    'country', 'month', 'city_norm_real', 'lob_base', 'segment',
                    'gap_trips_pct', 'gap_revenue_pct', 'alert_level'
                ]
                missing = [col for col in required_columns if col not in columns]
                if not missing:
                    results['passed'].append("✓ v_plan_vs_real_alerts_monthly_latest tiene todas las columnas requeridas")
                    print(f"  ✓ Columnas requeridas presentes ({len(required_columns)}/{len(required_columns)})")
                else:
                    results['failed'].append(f"❌ v_plan_vs_real_alerts_monthly_latest faltan columnas: {missing}")
                    print(f"  ✗ Faltan columnas: {missing}")
            except Exception as e:
                results['failed'].append(f"❌ Error verificando estructura: {str(e)}")
                print(f"  ✗ Error: {e}")
            
            # Test 7: Verificar status_bucket en v_plan_vs_real_monthly_latest
            print("[7/8] Verificando status_bucket en v_plan_vs_real_monthly_latest...")
            try:
                cursor.execute("""
                    SELECT status_bucket, COUNT(*) as cnt
                    FROM ops.v_plan_vs_real_monthly_latest
                    GROUP BY status_bucket
                    ORDER BY cnt DESC
                """)
                buckets = cursor.fetchall()
                valid_buckets = ['matched', 'plan_only', 'real_only', 'unknown']
                for bucket, cnt in buckets:
                    if bucket in valid_buckets:
                        print(f"  ✓ status_bucket '{bucket}': {cnt:,} registros")
                    else:
                        results['warnings'].append(f"⚠ status_bucket desconocido: '{bucket}' ({cnt} registros)")
                        print(f"  ⚠ status_bucket desconocido: '{bucket}': {cnt:,} registros")
                results['passed'].append("✓ status_bucket verificado")
            except Exception as e:
                results['failed'].append(f"❌ Error verificando status_bucket: {str(e)}")
                print(f"  ✗ Error: {e}")
            
            # Test 8: Verificar alert_level en v_plan_vs_real_alerts_monthly_latest
            print("[8/8] Verificando alert_level en v_plan_vs_real_alerts_monthly_latest...")
            try:
                cursor.execute("""
                    SELECT alert_level, COUNT(*) as cnt
                    FROM ops.v_plan_vs_real_alerts_monthly_latest
                    GROUP BY alert_level
                    ORDER BY cnt DESC
                """)
                levels = cursor.fetchall()
                valid_levels = ['CRITICO', 'MEDIO', 'OK']
                for level, cnt in levels:
                    if level in valid_levels:
                        print(f"  ✓ alert_level '{level}': {cnt:,} registros")
                    else:
                        results['warnings'].append(f"⚠ alert_level desconocido: '{level}' ({cnt} registros)")
                        print(f"  ⚠ alert_level desconocido: '{level}': {cnt:,} registros")
                results['passed'].append("✓ alert_level verificado")
            except Exception as e:
                results['failed'].append(f"❌ Error verificando alert_level: {str(e)}")
                print(f"  ✗ Error: {e}")
            
            # Resumen
            print()
            print("=" * 80)
            print("RESUMEN")
            print("=" * 80)
            print(f"✓ Pasados: {len(results['passed'])}")
            print(f"⚠ Warnings: {len(results['warnings'])}")
            print(f"✗ Fallidos: {len(results['failed'])}")
            print()
            
            if results['failed']:
                print("ERRORES:")
                for error in results['failed']:
                    print(f"  {error}")
                print()
            
            if results['warnings']:
                print("ADVERTENCIAS:")
                for warning in results['warnings']:
                    print(f"  {warning}")
                print()
            
            if len(results['failed']) == 0:
                print("✅ Todos los tests pasaron correctamente")
                return 0
            else:
                print("❌ Algunos tests fallaron")
                return 1
                
        except Exception as e:
            print(f"\n✗ Error fatal: {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            cursor.close()

if __name__ == "__main__":
    exit_code = smoke_test_views()
    sys.exit(exit_code)
