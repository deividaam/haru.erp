# admin_utils.py
from sqlalchemy.orm import Session
from database import SessionLocal, engine, create_tables # Importa la sesión y el motor
from models import Producto, PrecioProveedor, Categoria, Subcategoria, ContadorSKU, Base # Importa tus modelos

def borrar_todos_los_productos(db: Session, resetear_contadores_sku_param: bool = False): # Renombrado el parámetro para claridad
    """
    Elimina todos los productos, sus precios de proveedor asociados y,
    opcionalmente, resetea los contadores de SKU.
    ¡ADVERTENCIA: Esta acción es irreversible!
    """
    try:
        # 1. Eliminar Precios de Proveedor (dependen de Producto)
        num_precios_proveedor_borrados = db.query(PrecioProveedor).delete()
        print(f"Se eliminaron {num_precios_proveedor_borrados} registros de precios de proveedor.")

        # Aquí podrías añadir la eliminación de otros registros que dependan de Producto,
        # como historial_compras, inventario, etc., si los implementas.
        # Ejemplo:
        # num_historial_borrado = db.query(HistorialCompra).delete()
        # print(f"Se eliminaron {num_historial_borrado} registros de historial de compras.")

        # 2. Eliminar Productos
        num_productos_borrados = db.query(Producto).delete()
        print(f"Se eliminaron {num_productos_borrados} productos.")

        if resetear_contadores_sku_param: # Usar el nombre del parámetro
            # 3. Opcional: Resetear contadores de SKU a 0
            num_contadores_reseteados = db.query(ContadorSKU).update({"ultimo_valor": 0})
            print(f"Se resetearon {num_contadores_reseteados} contadores de SKU a 0.")
        
        db.commit()
        print("¡Todos los productos y datos asociados han sido eliminados exitosamente!")
        if resetear_contadores_sku_param: # Usar el nombre del parámetro
            print("Los contadores de SKU también han sido reseteados.")

    except Exception as e:
        db.rollback()
        print(f"Error al borrar los productos: {e}")
        print("Se ha hecho rollback de la transacción.")

def borrar_todas_las_tablas_de_datos_transaccionales():
    """
    Elimina datos de tablas transaccionales como productos, precios,
    pero MANTIENE tablas maestras como categorías y proveedores.
    También resetea contadores SKU.
    ¡ADVERTENCIA: Esta acción es irreversible!
    """
    db = SessionLocal()
    try:
        print("\n--- Iniciando borrado de datos transaccionales ---")
        # El orden es importante debido a las claves foráneas
        
        # 1. Tablas que dependen de Producto
        count = db.query(PrecioProveedor).delete()
        print(f"- {count} precios de proveedor eliminados.")
        # Añadir aquí otras tablas que dependan de Producto (ej. historial_compras, inventario_items)

        # 2. Tabla de Productos
        count = db.query(Producto).delete()
        print(f"- {count} productos eliminados.")

        # 3. Resetear Contadores SKU
        count = db.query(ContadorSKU).update({"ultimo_valor": 0})
        print(f"- {count} contadores SKU reseteados a 0.")
        
        db.commit()
        print("--- Borrado de datos transaccionales completado exitosamente. ---")
        print("Las tablas de Categorías, Subcategorías y Proveedores NO fueron afectadas.")

    except Exception as e:
        db.rollback()
        print(f"Error durante el borrado de datos transaccionales: {e}")
    finally:
        db.close()


def resetear_base_de_datos_completa():
    """
    ¡PELIGROSO! Elimina TODAS las tablas definidas en los modelos y las vuelve a crear.
    Esto borrará TODOS LOS DATOS.
    """
    print("\n--- ADVERTENCIA: ESTA ACCIÓN BORRARÁ TODOS LOS DATOS Y RECREARÁ LAS TABLAS ---")
    confirmacion = input("Escribe 'SI, ESTOY SEGURO' para continuar: ")
    if confirmacion == "SI, ESTOY SEGURO":
        try:
            print("Eliminando todas las tablas...")
            Base.metadata.drop_all(bind=engine)
            print("Tablas eliminadas.")
            print("Creando todas las tablas de nuevo...")
            Base.metadata.create_all(bind=engine) 
            print("Tablas recreadas exitosamente.")
            print("La base de datos ha sido reseteada.")
        except Exception as e:
            print(f"Error al resetear la base de datos: {e}")
    else:
        print("Reseteo de base de datos cancelado.")


if __name__ == "__main__":
    print("Utilidad de Administración de Base de Datos Haru ERP")
    print("----------------------------------------------------")
    print("Opciones:")
    print("  1. Borrar TODOS los productos y sus precios (opcionalmente resetear contadores SKU)")
    print("  2. Borrar datos transaccionales (productos, precios, resetear contadores SKU) - MANTIENE CAT/SUB/PROV")
    print("  3. ¡PELIGRO! Resetear TODA la base de datos (borrar todas las tablas y recrearlas)")
    print("  0. Salir")

    opcion = input("Selecciona una opción: ")

    if opcion == '1':
        confirm = input("¿Estás SEGURO de que quieres borrar todos los productos y sus precios? (escribe 'si' para confirmar): ").lower()
        if confirm == 'si':
            reset_sku_input = input("¿Quieres resetear también los contadores de SKU a 0? (escribe 'si' para confirmar): ").lower() # Renombrada para evitar confusión
            db_session = SessionLocal()
            try:
                # CORRECCIÓN AQUÍ: Usar la variable correcta 'reset_sku_input'
                borrar_todos_los_productos(db_session, reset_sku_input == 'si')
            finally:
                db_session.close()
        else:
            print("Operación cancelada.")
    
    elif opcion == '2':
        confirm = input("¿Estás SEGURO de que quieres borrar productos, precios y resetear SKUs (MANTENIENDO Categorías, Subcategorías y Proveedores)? (escribe 'si' para confirmar): ").lower()
        if confirm == 'si':
            borrar_todas_las_tablas_de_datos_transaccionales()
        else:
            print("Operación cancelada.")

    elif opcion == '3':
        resetear_base_de_datos_completa()
        
    elif opcion == '0':
        print("Saliendo.")
    else:
        print("Opción no válida.")
