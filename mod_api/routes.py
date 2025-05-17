# /mod_api/routes.py
from flask import jsonify
from sqlalchemy.orm import Session
from . import api_bp # Importar el blueprint
from database import SessionLocal # Acceso a la sesión de la BD
from models import Categoria, Subcategoria # Modelos necesarios

# Estructura de configuración detallada (temporalmente hardcodeada aquí)
# En una aplicación real, esto vendría de la base de datos o un archivo de configuración.
DETAILED_CATEGORY_CONFIG_DATA = [
  {
    "categoriaNombre": "Dulces/Golosinas", # Este nombre debe coincidir exactamente con el de la BD
    "camposRequeridos": ["SubcategoriaEspecifica", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Sabor", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "DescripcionAdicionalInterna", "Marca"],
    "opcionesPresentacion": ["Bolsa", "Caja", "Bote", "Pieza", "Paquete", "A Granel"],
    "opcionesUnidadMedidaBase": ["Bolsa", "Caja", "Bote", "Pieza", "Paquete", "kg", "g", "Litro", "ml", "Porción"], # Nota: UnidadMedidaBase suele ser más fundamental (g, ml, pieza)
    "opcionesMaterial": [] 
  },
  {
    "categoriaNombre": "Globos", # Este nombre debe coincidir exactamente con el de la BD
    "subcategoriasPermitidas": ["Látex", "Metálico", "Mate", "Perlado", "Burbuja", "Temático", "De Cumpleaños", "De Baby Shower", "De Boda", "De XV años"], # Sobrescribirá las de la BD si se define aquí
    "camposRequeridos": ["SubcategoriaEspecifica", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Color", "Tamano", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Material", "DescripcionAdicionalInterna", "Marca"],
    "opcionesPresentacion": ["Pieza", "Paquete", "Arreglo"],
    "opcionesUnidadMedidaBase": ["Pieza", "Paquete"],
    "opcionesMaterial": ["Látex", "Mylar/Foil", "Burbuja", "Plástico"]
  },
  {
    "categoriaNombre": "Decoración", # Este nombre debe coincidir exactamente con el de la BD
    "camposRequeridos": ["SubcategoriaEspecifica", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "Color", "DiasAnticipacionCompra"],
    "camposOpcionales": ["DimensionesCapacidad", "Material", "TemaEstilo", "DescripcionAdicionalInterna", "FormaTipo", "Marca"],
    "opcionesPresentacion": ["Pieza", "Juego/Set", "Rollo", "Metro", "Paquete"],
    "opcionesUnidadMedidaBase": ["Pieza", "Juego/Set", "Rollo", "m", "cm", "Paquete"],
    "opcionesMaterial": ["Papel", "Tela", "Plástico", "Madera", "Metal", "Flor Natural", "Flor Artificial"]
  },
  {
    "categoriaNombre": "Display", # Este nombre debe coincidir exactamente con el de la BD
    "camposRequeridos": ["SubcategoriaEspecifica", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "Color", "Material", "DiasAnticipacionCompra"],
    "camposOpcionales": ["DimensionesCapacidad", "FormaTipo", "DescripcionAdicionalInterna", "Marca"],
    "opcionesPresentacion": ["Pieza", "Juego/Set"],
    "opcionesUnidadMedidaBase": ["Pieza", "Juego/Set"],
    "opcionesMaterial": ["Vidrio", "Plástico", "Acrílico", "Metal", "Madera", "Cartón"]
  },
  {
    # Ejemplo si tuvieras una categoría para "Servicios" como productos internos (raro, pero para mostrar)
    "categoriaNombre": "Servicios Internos de Apoyo", # Ej: "Transporte Base", "Hora de Montador"
    "camposRequeridos": ["SubcategoriaEspecifica", "NombreProducto", "UnidadMedidaBase", "DiasAnticipacionCompra"],
    "camposOpcionales": ["DescripcionAdicionalInterna"],
    "opcionesUnidadMedidaBase": ["Hora", "Viaje", "Servicio", "Paquete"],
    # "opcionesModalidadServicio": ["Por evento", "Por hora", "Por persona", "Por paquete"] # Si fuera relevante
  }
]

@api_bp.route('/product-categories-config', methods=['GET'])
def get_product_categories_config():
    db = SessionLocal()
    try:
        categorias_principales_db = db.query(Categoria)\
                                   .filter(Categoria.id_categoria_padre == None)\
                                   .order_by(Categoria.nombre_categoria)\
                                   .all()
        
        config_para_sheets = []
        for cat_db in categorias_principales_db:
            # Buscar la configuración detallada hardcodeada para esta categoría
            config_detallada_cat = next((item for item in DETAILED_CATEGORY_CONFIG_DATA if item["categoriaNombre"] == cat_db.nombre_categoria), None)

            subcategorias_directas_query = db.query(Subcategoria.nombre_subcategoria)\
                                             .filter(Subcategoria.id_categoria_contenedora == cat_db.id_categoria,
                                                     Subcategoria.id_subcategoria_padre == None)\
                                             .order_by(Subcategoria.nombre_subcategoria)\
                                             .all()
            nombres_subcategorias_db = [s[0] for s in subcategorias_directas_query]

            # Construir el objeto de configuración para esta categoría
            config_cat_api = {
                "categoriaNombre": cat_db.nombre_categoria,
                # Usar subcategorías de la config hardcodeada si existen, sino de la BD
                "subcategoriasPermitidas": config_detallada_cat.get("subcategoriasPermitidas", nombres_subcategorias_db) if config_detallada_cat else nombres_subcategorias_db,
                # Añadir los demás campos desde la config hardcodeada si existe
                "camposRequeridos": config_detallada_cat.get("camposRequeridos", []) if config_detallada_cat else [],
                "camposOpcionales": config_detallada_cat.get("camposOpcionales", []) if config_detallada_cat else [],
                "opcionesPresentacion": config_detallada_cat.get("opcionesPresentacion", []) if config_detallada_cat else [],
                "opcionesUnidadMedidaBase": config_detallada_cat.get("opcionesUnidadMedidaBase", []) if config_detallada_cat else [], # Cambiado de UnidadMedidaVenta
                "opcionesMaterial": config_detallada_cat.get("opcionesMaterial", []) if config_detallada_cat else [],
                "opcionesModalidadServicio": config_detallada_cat.get("opcionesModalidadServicio", []) if config_detallada_cat else [] # Si aplica
            }
            config_para_sheets.append(config_cat_api)
            
        return jsonify(config_para_sheets)

    except Exception as e:
        print(f"Error en API /product-categories-config: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error interno del servidor al obtener categorías: {str(e)}"}), 500
    finally:
        if db.is_active:
            db.close()
