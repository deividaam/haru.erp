# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env (si existe)
# Esto permite definir las credenciales de la BD fuera del código.
load_dotenv()

# --- Configuración de la Base de Datos con Variables Separadas ---
# Intenta leer cada parte de la conexión desde variables de entorno.
# Proporciona valores por defecto si no se encuentran (ajusta según tu configuración local).

DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "Minju125116532") # ¡CAMBIA ESTO EN .env O AQUÍ SI ES NECESARIO!
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "haru_erp_test") # El nombre de tu base de datos

# Construir la DATABASE_URL dinámicamente
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"Intentando conectar a la base de datos: postgresql://{DB_USER}:****@{DB_HOST}:{DB_PORT}/{DB_NAME}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    """Generador para obtener una sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Importa Base de models.py para crear las tablas
# Asegúrate de que models.py esté en el mismo directorio o en el PYTHONPATH
try:
    from models import Base
except ImportError:
    print("Advertencia: No se pudo importar 'Base' desde 'models'. Asegúrate de que models.py exista y esté accesible.")
    Base = None # Para evitar errores si se llama create_tables sin Base

def create_tables():
    """Crea todas las tablas en la base de datos si no existen."""
    if Base is None:
        print("Error: No se pueden crear tablas porque 'Base' de SQLAlchemy no está definida (models.py no se importó correctamente).")
        return
        
    try:
        Base.metadata.create_all(bind=engine)
        print("Tablas creadas exitosamente (si no existían).")
    except Exception as e:
        print(f"Error al crear las tablas: {e}")
        print("Detalles de la conexión usada:")
        print(f"  Usuario: {DB_USER}")
        print(f"  Host: {DB_HOST}")
        print(f"  Puerto: {DB_PORT}")
        print(f"  Base de datos: {DB_NAME}")
        print("Verifica que el servidor PostgreSQL esté corriendo, que la base de datos exista,")
        print("y que las credenciales y detalles de conexión sean correctos en tu archivo .env o en database.py.")


if __name__ == "__main__":
    # Esto se ejecutará si corres database.py directamente
    # Útil para crear las tablas la primera vez o para probar la conexión.
    print("Intentando crear tablas desde database.py...")
    create_tables()
    
    # Prueba de conexión simple
    try:
        connection = engine.connect()
        print("¡Conexión a la base de datos exitosa!")
        connection.close()
    except Exception as e:
        print(f"Falló la prueba de conexión a la base de datos: {e}")

