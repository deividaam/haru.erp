# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env (si existe)
# Esto permite definir las credenciales de la BD fuera del código.
load_dotenv()

# Utiliza directamente la variable de entorno DATABASE_URL
# Esta será la URL que obtuviste de Supabase.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("No se encontró la variable de entorno DATABASE_URL. Asegúrate de que esté configurada.")

print(f"Intentando conectar a la base de datos configurada en DATABASE_URL...")

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

