"""
Script para verificar y corregir la codificación del archivo .env.
Lee el archivo con diferentes codificaciones y muestra qué variables tienen problemas.
"""

import os
import sys

def check_env_file():
    """Verifica la codificación del archivo .env."""
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    
    if not os.path.exists(env_file):
        print(f"❌ Archivo .env no encontrado: {env_file}")
        return
    
    print(f"📄 Verificando archivo: {env_file}\n")
    
    # Intentar leer con diferentes codificaciones
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            with open(env_file, 'r', encoding=encoding) as f:
                content = f.read()
            print(f"✓ Legible con codificación: {encoding}")
            
            # Verificar variables de base de datos
            lines = content.split('\n')
            db_vars = {}
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key in ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME', 'DATABASE_URL']:
                        db_vars[key] = value
            
            if db_vars:
                print(f"\n📋 Variables de base de datos encontradas:")
                for key, value in db_vars.items():
                    if key == 'DB_PASSWORD':
                        print(f"   {key}: {'*' * min(len(value), 10)}")
                    elif key == 'DATABASE_URL':
                        # Ocultar password en URL
                        if '@' in value:
                            safe_url = value.split('@')[0].split(':')[:-1]
                            safe_url = ':'.join(safe_url) + ':***@' + value.split('@')[1]
                            print(f"   {key}: {safe_url}")
                        else:
                            print(f"   {key}: {value[:50]}...")
                    else:
                        print(f"   {key}: {value}")
                    
                    # Verificar codificación UTF-8
                    try:
                        value.encode('utf-8')
                    except UnicodeEncodeError as e:
                        print(f"      ⚠️  PROBLEMA: No se puede codificar en UTF-8")
                        print(f"         Posición problemática: {e.start}-{e.end}")
                        print(f"         Valor: {repr(value)}")
            
            break
        except UnicodeDecodeError:
            continue
    else:
        print("❌ No se pudo leer el archivo con ninguna codificación estándar")
        return
    
    print("\n" + "=" * 60)
    print("RECOMENDACIONES:")
    print("=" * 60)
    print("1. Si hay problemas de codificación, guarda el archivo .env en UTF-8")
    print("2. Si usas caracteres especiales, considera usar DATABASE_URL directamente")
    print("3. Ejemplo de DATABASE_URL:")
    print("   DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/yego_integral")
    print("=" * 60)

if __name__ == "__main__":
    check_env_file()
