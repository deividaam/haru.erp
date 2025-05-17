# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv() # Carga variables desde .env para desarrollo local

# Utiliza directamente la variable de entorno DATABASE_URL
# Esta será la URL que obtuviste de Supabase.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("No se encontró la variable de entorno DATABASE_URL. Asegúrate de que esté configurada.")

print(f"Intentando conectar a la base de datos configurada en DATABASE_URL...")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

try:
    from models import Base
except ImportError:
    print("Advertencia: No se pudo importar 'Base' desde 'models'. Asegúrate de que models.py exista y esté accesible.")
    Base = None

def create_tables():
    if Base is None:
        print("Error: No se pueden crear tablas porque 'Base' de SQLAlchemy no está definida.")
        return
    try:
        Base.metadata.create_all(bind=engine)
        print("Tablas creadas exitosamente (si no existían) en la base de datos configurada.")
    except Exception as e:
        print(f"Error al crear las tablas: {e}")
        print("Verifica que la DATABASE_URL sea correcta y que la base de datos Supabase esté accesible.")

if __name__ == "__main__":
    print("Intentando crear tablas desde database.py (esto no se ejecutará en Render)...")
    # No es ideal llamar a create_tables() directamente aquí para producción.
    # Es mejor manejarlo con un script de build o un comando de Flask.
    # create_tables() # Comentado para evitar ejecución automática no deseada
    
    # Prueba de conexión simple
    if DATABASE_URL:
        try:
            connection = engine.connect()
            print("¡Conexión a la base de datos (Supabase) exitosa!")
            connection.close()
        except Exception as e:
            print(f"Falló la prueba de conexión a la base de datos (Supabase): {e}")
    else:
        print("DATABASE_URL no está configurada. No se puede probar la conexión.")