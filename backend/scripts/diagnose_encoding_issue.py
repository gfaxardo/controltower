"""
Script de diagnóstico para identificar problemas de codificación UTF-8
en las variables de entorno de la base de datos.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose_encoding():
    """Diagnostica problemas de codificación en las variables de entorno."""
    
    print("=" * 60)
    print("DIAGNÓSTICO DE CODIFICACIÓN - Variables de Base de Datos")
    print("=" * 60)
    
    # Verificar variables individuales
    vars_to_check = {
        'DB_HOST': settings.DB_HOST,
        'DB_PORT': settings.DB_PORT,
        'DB_NAME': settings.DB_NAME,
        'DB_USER': settings.DB_USER,
        'DB_PASSWORD': '***' if settings.DB_PASSWORD else '',  # No mostrar password completo
        'DATABASE_URL': settings.DATABASE_URL[:50] + '...' if settings.DATABASE_URL and len(settings.DATABASE_URL) > 50 else settings.DATABASE_URL
    }
    
    print("\n1. Variables de configuración:")
    for var_name, var_value in vars_to_check.items():
        if var_value:
            try:
                # Intentar codificar en UTF-8
                if isinstance(var_value, str):
                    encoded = var_value.encode('utf-8')
                    print(f"   ✓ {var_name}: OK (longitud: {len(var_value)}, bytes UTF-8: {len(encoded)})")
                else:
                    print(f"   ✓ {var_name}: {var_value} (tipo: {type(var_value).__name__})")
            except UnicodeEncodeError as e:
                print(f"   ✗ {var_name}: ERROR de codificación - {e}")
                print(f"      Valor problemático: {repr(var_value)}")
        else:
            print(f"   - {var_name}: (vacío)")
    
    # Verificar archivo .env si existe
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    print(f"\n2. Archivo .env:")
    if os.path.exists(env_file):
        print(f"   ✓ Archivo existe: {env_file}")
        try:
            # Intentar leer con diferentes codificaciones
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    with open(env_file, 'r', encoding=encoding) as f:
                        content = f.read()
                    print(f"   ✓ Legible con codificación: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                print(f"   ✗ No se pudo leer con ninguna codificación estándar")
        except Exception as e:
            print(f"   ✗ Error al leer archivo: {e}")
    else:
        print(f"   - Archivo no existe: {env_file}")
        print(f"   - Usando variables de entorno del sistema")
    
    # Verificar construcción de URL
    print(f"\n3. Construcción de URL de conexión:")
    try:
        from urllib.parse import quote_plus
        
        if settings.DATABASE_URL:
            url = settings.DATABASE_URL
            print(f"   ✓ Usando DATABASE_URL directamente")
        else:
            db_user = quote_plus(settings.DB_USER) if settings.DB_USER else ''
            db_password = quote_plus(settings.DB_PASSWORD) if settings.DB_PASSWORD else ''
            url = f"postgresql://{db_user}:{db_password}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            print(f"   ✓ URL construida desde variables individuales")
        
        # Mostrar URL sin password para diagnóstico
        if '@' in url:
            url_safe = url.split('@')[0].split(':')[:-1]
            url_safe = ':'.join(url_safe) + ':***@' + url.split('@')[1]
        else:
            url_safe = url
        print(f"   URL (sin password): {url_safe}")
        
        # Verificar que la URL se puede codificar
        try:
            url_bytes = url.encode('utf-8')
            print(f"   ✓ URL codificable en UTF-8 (longitud: {len(url_bytes)} bytes)")
        except UnicodeEncodeError as e:
            print(f"   ✗ ERROR: URL no codificable en UTF-8 - {e}")
            print(f"      Posición problemática: {e.start}-{e.end}")
            
    except Exception as e:
        print(f"   ✗ Error al construir URL: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("RECOMENDACIONES:")
    print("=" * 60)
    print("1. Si hay errores de codificación, verifica que el archivo .env esté en UTF-8")
    print("2. Si usas caracteres especiales en DB_USER o DB_PASSWORD, asegúrate de que")
    print("   estén correctamente codificados en UTF-8")
    print("3. Considera usar DATABASE_URL directamente en lugar de variables individuales")
    print("4. Si el problema persiste, verifica la codificación del sistema operativo")
    print("=" * 60)

if __name__ == "__main__":
    diagnose_encoding()
