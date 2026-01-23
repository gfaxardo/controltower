from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from urllib.parse import quote_plus
import logging

logger = logging.getLogger(__name__)

def safe_encode(value: str) -> str:
    """Codifica de forma segura un valor para URL, manejando caracteres especiales."""
    if not value:
        return ''
    try:
        # Asegurar que el valor esté en formato string y en UTF-8 válido
        if isinstance(value, bytes):
            # Intentar decodificar desde diferentes codificaciones
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    value = value.decode(encoding)
                    break
                except (UnicodeDecodeError, AttributeError):
                    continue
            else:
                # Fallback: reemplazar caracteres inválidos
                value = value.decode('utf-8', errors='replace')
        
        # Si es string, asegurar que se pueda codificar en UTF-8
        if isinstance(value, str):
            try:
                # Verificar que se puede codificar en UTF-8
                value.encode('utf-8')
            except UnicodeEncodeError:
                # Intentar convertir desde otras codificaciones
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        # Asumir que el string está en esa codificación y convertir a UTF-8
                        value = value.encode(encoding).decode('utf-8')
                        break
                    except:
                        continue
                else:
                    # Fallback: reemplazar caracteres problemáticos
                    value = value.encode('utf-8', errors='replace').decode('utf-8')
        
        # quote_plus ya maneja la codificación URL correctamente
        return quote_plus(value)
    except Exception as e:
        logger.warning(f"Error al codificar valor: {e}")
        # Fallback: intentar codificar directamente
        try:
            # Último recurso: convertir a string y reemplazar caracteres problemáticos
            str_value = str(value)
            str_value = str_value.encode('utf-8', errors='replace').decode('utf-8')
            return quote_plus(str_value)
        except:
            return ''

if settings.DATABASE_URL:
    # Si DATABASE_URL está configurado, asegurar que esté en UTF-8 válido
    try:
        database_url = settings.DATABASE_URL
        # Verificar que se puede codificar
        database_url.encode('utf-8')
    except (UnicodeEncodeError, AttributeError):
        # Intentar convertir desde otras codificaciones
        for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
            try:
                database_url = settings.DATABASE_URL.encode(encoding).decode('utf-8')
                break
            except:
                continue
        else:
            # Fallback: reemplazar caracteres problemáticos
            database_url = settings.DATABASE_URL.encode('utf-8', errors='replace').decode('utf-8')
else:
    db_user = safe_encode(settings.DB_USER) if settings.DB_USER else ''
    db_password = safe_encode(settings.DB_PASSWORD) if settings.DB_PASSWORD else ''
    db_host = safe_encode(settings.DB_HOST) if settings.DB_HOST else 'localhost'
    db_port = settings.DB_PORT or 5432
    db_name = safe_encode(settings.DB_NAME) if settings.DB_NAME else ''
    
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # Verificar que la URL final se puede codificar en UTF-8
    try:
        database_url.encode('utf-8')
    except UnicodeEncodeError:
        logger.error("ERROR: La URL de conexión contiene caracteres no válidos en UTF-8")
        logger.error("Verifica que el archivo .env esté en UTF-8 o usa DATABASE_URL directamente")
        raise

# Use attributes directly to avoid ConfigParser interpolation issues with special characters
config.attributes['sqlalchemy.url'] = database_url

target_metadata = None

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    def ensure_utf8_param(value):
        """Asegura que un parámetro esté en UTF-8 válido."""
        if not value:
            return value
        if isinstance(value, str):
            try:
                value.encode('utf-8')
                return value
            except UnicodeEncodeError:
                # Intentar convertir desde otras codificaciones
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        # Asumir que está en esa codificación y convertir a UTF-8
                        return value.encode(encoding).decode('utf-8')
                    except:
                        continue
                # Fallback: reemplazar caracteres problemáticos
                return value.encode('utf-8', errors='replace').decode('utf-8')
        return str(value)
    
    # Si no hay DATABASE_URL, usar siempre conexión directa para evitar problemas de codificación
    # con la construcción de URL desde variables individuales
    if not settings.DATABASE_URL:
        logger.info("DATABASE_URL no configurado, usando conexión directa con parámetros individuales")
        use_direct_connection = True
    else:
        # Si hay DATABASE_URL, intentar usarlo
        url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
        
        # Verificar si podemos usar la URL directamente
        use_direct_connection = False
        try:
            # Intentar codificar la URL para verificar que es válida en UTF-8
            if isinstance(url, str):
                url.encode('utf-8')
            # Si llegamos aquí, la URL es válida en UTF-8
            use_direct_connection = False
        except (UnicodeEncodeError, UnicodeDecodeError, AttributeError) as e:
            # Si hay problemas de codificación con la URL, usar conexión directa
            logger.warning(f"Problema de codificación detectado con URL, usando parámetros directos: {type(e).__name__}")
            use_direct_connection = True
    
    if use_direct_connection:
        # Usar psycopg2 directamente con parámetros individuales y crear engine de SQLAlchemy
        import psycopg2
        
        try:
            # Obtener valores y asegurar UTF-8
            conn_params = {
                'host': ensure_utf8_param(settings.DB_HOST) or 'localhost',
                'port': settings.DB_PORT or 5432,
                'database': ensure_utf8_param(settings.DB_NAME) or '',
                'user': ensure_utf8_param(settings.DB_USER) or '',
                'password': ensure_utf8_param(settings.DB_PASSWORD) or '',
                'client_encoding': 'UTF8'
            }
            
            # Crear conexión directa
            raw_conn = psycopg2.connect(**conn_params)
            
            # Crear engine de SQLAlchemy usando la conexión raw
            # Usamos un DSN básico sin password para evitar problemas de codificación
            dsn = f"postgresql://{conn_params['user']}@{conn_params['host']}:{conn_params['port']}/{conn_params['database']}"
            
            # Crear engine con creator que devuelve la conexión raw
            def creator():
                return raw_conn
            
            connectable = create_engine(
                'postgresql://',
                poolclass=pool.NullPool,
                creator=creator,
                connect_args={'client_encoding': 'UTF8'}
            )
            
            # Usar esta conexión para las migraciones
            with connectable.connect() as connection:
                context.configure(
                    connection=connection, 
                    target_metadata=target_metadata
                )
                
                with context.begin_transaction():
                    context.run_migrations()
            
            raw_conn.close()
            return
        except Exception as e:
            logger.error(f"Error al conectar directamente con psycopg2: {e}")
            logger.error("Solución: Usa DATABASE_URL en tu archivo .env en lugar de variables individuales")
            logger.error("Ejemplo: DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/yego_integral")
            raise
    
    # Si llegamos aquí, usar la URL normalmente (solo si hay DATABASE_URL)
    url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    connect_args = {
        'client_encoding': 'utf8'
    }
    
    try:
        connectable = create_engine(
            url, 
            poolclass=pool.NullPool,
            connect_args=connect_args
        )
        
        # Intentar conectar - si falla por codificación, usar conexión directa
        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        # Si hay error de codificación, usar conexión directa como fallback
        logger.warning(f"Error de codificación UTF-8 detectado al usar URL, cambiando a conexión directa: {e}")
        
        # Usar psycopg2 directamente con parámetros individuales y crear engine de SQLAlchemy
        import psycopg2
        
        try:
            # Obtener valores y asegurar UTF-8
            conn_params = {
                'host': ensure_utf8_param(settings.DB_HOST) or 'localhost',
                'port': settings.DB_PORT or 5432,
                'database': ensure_utf8_param(settings.DB_NAME) or '',
                'user': ensure_utf8_param(settings.DB_USER) or '',
                'password': ensure_utf8_param(settings.DB_PASSWORD) or '',
                'client_encoding': 'UTF8'
            }
            
            # Crear conexión directa
            raw_conn = psycopg2.connect(**conn_params)
            
            # Crear engine de SQLAlchemy usando la conexión raw
            # Usamos un DSN básico sin password para evitar problemas de codificación
            def creator():
                return raw_conn
            
            connectable = create_engine(
                'postgresql://',
                poolclass=pool.NullPool,
                creator=creator,
                connect_args={'client_encoding': 'UTF8'}
            )
            
            # Usar esta conexión para las migraciones
            with connectable.connect() as connection:
                context.configure(
                    connection=connection, 
                    target_metadata=target_metadata
                )
                
                with context.begin_transaction():
                    context.run_migrations()
            
            raw_conn.close()
        except Exception as e2:
            logger.error(f"Error al conectar directamente con psycopg2: {e2}")
            logger.error("Solución: Usa DATABASE_URL en tu archivo .env en lugar de variables individuales")
            logger.error("Ejemplo: DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/yego_integral")
            raise
    except Exception as e:
        logger.error(f"Error al crear engine de SQLAlchemy: {e}")
        logger.error(f"URL (sin password): {url.split('@')[1] if '@' in url else url}")
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
