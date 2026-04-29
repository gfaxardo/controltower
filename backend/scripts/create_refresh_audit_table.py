#!/usr/bin/env python3
"""
Script para crear la tabla de auditoría de refresh.
Ejecutar: python scripts/create_refresh_audit_table.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.connection import get_db


def create_refresh_audit_table():
    """Crea la tabla bi.refresh_audit si no existe."""
    sql = """
    -- Crear schema bi si no existe
    CREATE SCHEMA IF NOT EXISTS bi;
    
    -- Crear tabla de auditoría de refresh
    CREATE TABLE IF NOT EXISTS bi.refresh_audit (
        id SERIAL PRIMARY KEY,
        dataset_name TEXT NOT NULL,
        last_refresh_at TIMESTAMP NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
        duration_seconds NUMERIC(10, 2),
        error_message TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Crear índices
    CREATE INDEX IF NOT EXISTS idx_refresh_audit_dataset 
        ON bi.refresh_audit(dataset_name);
    
    CREATE INDEX IF NOT EXISTS idx_refresh_audit_created_at 
        ON bi.refresh_audit(created_at DESC);
    
    -- Comentario de documentación
    COMMENT ON TABLE bi.refresh_audit IS 'Auditoría de refresh de materialized views y datasets';
    """
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            cursor.close()
        print("✅ Tabla bi.refresh_audit creada/actualizada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error creando tabla: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("CREANDO TABLA DE AUDITORÍA DE REFRESH")
    print("=" * 60)
    success = create_refresh_audit_table()
    sys.exit(0 if success else 1)
