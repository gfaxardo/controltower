#!/usr/bin/env python3
"""
Script para crear la tabla de lock anti-concurrencia.
Ejecutar: python scripts/create_refresh_lock_table.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.connection import get_db


def create_refresh_lock_table():
    """Crea la tabla bi.refresh_lock si no existe."""
    sql = """
    -- Crear schema bi si no existe
    CREATE SCHEMA IF NOT EXISTS bi;
    
    -- Crear tabla de lock anti-concurrencia
    CREATE TABLE IF NOT EXISTS bi.refresh_lock (
        id SERIAL PRIMARY KEY,
        lock_name TEXT NOT NULL DEFAULT 'global',
        is_running BOOLEAN NOT NULL DEFAULT FALSE,
        started_at TIMESTAMP,
        updated_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Crear índice único por lock_name
    CREATE UNIQUE INDEX IF NOT EXISTS idx_refresh_lock_name 
        ON bi.refresh_lock(lock_name);
    
    -- Insertar registro inicial si no existe
    INSERT INTO bi.refresh_lock (lock_name, is_running, updated_at)
    VALUES ('global', FALSE, NOW())
    ON CONFLICT (lock_name) DO NOTHING;
    
    -- Comentario de documentación
    COMMENT ON TABLE bi.refresh_lock IS 'Lock anti-concurrencia para evitar ejecución paralela de refresh jobs';
    """
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            cursor.close()
        print("✅ Tabla bi.refresh_lock creada/actualizada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error creando tabla: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("CREANDO TABLA DE LOCK ANTI-CONCURRENCIA")
    print("=" * 60)
    success = create_refresh_lock_table()
    sys.exit(0 if success else 1)
