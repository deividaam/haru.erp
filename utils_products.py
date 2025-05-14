# utils_productos.py (o añadir a utils_carga.py)
from sqlalchemy.orm import Session
from models import Producto, Categoria, Subcategoria # Asegúrate que models.py esté accesible
# Importar get_or_create_categoria, get_or_create_subcategoria, generar_siguiente_sku, construir_descripcion_completa
# si esta lógica también se usa al editar (ej. si se cambia la categoría y se necesita regenerar SKU o descripción)
# Por ahora, asumimos que SKU y desc_completa no se regeneran en una simple edición de otros campos.

def get_producto_by_id(db: Session, id_producto: int) -> Producto | None:
    """Obtiene un producto por su ID."""
    return db.query(Producto).filter(Producto.id_producto == id_producto).first()

def update_producto(db: Session, id_producto: int, datos_actualizacion: dict) -> Producto | None:
    """Actualiza un producto existente."""
    producto_db = get_producto_by_id(db, id_producto)
    if not producto_db:
        return None

    # Campos que se pueden actualizar (excluir SKU por ahora, ya que es generado)
    campos_actualizables = [
        "nombre_producto", "descripcion_adicional", "presentacion", 
        "cantidad_por_presentacion", "unidad_medida_venta", "sabor", "color", 
        "tamano_pulgadas", "material", "dimensiones_capacidad", "tema_estilo",
        "modalidad_servicio", "activo"
        # Considerar si se puede cambiar categoría/subcategoría y cómo afectaría al SKU
    ]

    for campo in campos_actualizables:
        if campo in datos_actualizacion:
            setattr(producto_db, campo, datos_actualizacion[campo])
    
    # Regenerar descripción completa si los campos relevantes cambiaron
    # Convertir el objeto producto_db a un diccionario para pasarlo a construir_descripcion_completa
    # o modificar construir_descripcion_completa para que acepte el objeto Producto.
    # Aquí una forma simple:
    datos_para_desc = {c.name: getattr(producto_db, c.name) for c in producto_db.__table__.columns if hasattr(producto_db, c.name)}
    from utils_carga import construir_descripcion_completa # Asumiendo que está en utils_carga
    producto_db.descripcion_completa_generada = construir_descripcion_completa(datos_para_desc)


    try:
        db.commit()
        db.refresh(producto_db)
        return producto_db
    except Exception as e:
        db.rollback()
        print(f"Error al actualizar producto ID {id_producto}: {e}")
        raise e # Re-lanzar la excepción para que la ruta de Flask la maneje
