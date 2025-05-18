# /mod_api/routes.py
from flask import jsonify
from sqlalchemy.orm import Session, selectinload
from . import api_bp
from database import SessionLocal
from models import Categoria, Subcategoria

# Lista predefinida de las 7 Categorías Principales
PREDEFINED_MAIN_CATEGORIES_NAMES = [
    "Comestibles",
    "Art. Fiesta",
    "Material Deco",
    "Display",
    "Mobiliario",
    "Papelería",
    "Servicios"
]

# Estructura de configuración detallada.
# Los "categoriaNombre" DEBEN coincidir con los nombres en PREDEFINED_MAIN_CATEGORIES_NAMES
# y también con los nombres que eventualmente tendrás en tu tabla 'categorias' de la BD.
DETAILED_CATEGORY_CONFIG_DATA = [
  {
    "categoriaNombre": "Comestibles",
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Sabor", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Bolsa", "Caja", "Bote", "Pieza", "Paquete", "A Granel", "Kg", "g", "Litro", "ml"],
    "opcionesUnidadMedidaBase": ["Pieza", "Paquete", "kg", "g", "Litro", "ml", "Porción"],
    "opcionesMaterial": []
  },
  {
    "categoriaNombre": "Art. Fiesta",
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Color", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Tamano", "Material", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Pieza", "Paquete", "Set", "Bolsa"],
    "opcionesUnidadMedidaBase": ["Pieza", "Paquete", "Set", "Unidad"],
    "opcionesMaterial": ["Látex", "Metálico/Foil", "Plástico", "Papel", "Cartón"]
  },
  {
    "categoriaNombre": "Material Deco",
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Color", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Dimensiones", "Material", "TemaEstilo", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Pieza", "Juego/Set", "Rollo", "Metro", "Paquete", "Unidad"],
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Rollo", "m", "cm", "Unidad", "g", "kg"],
    "opcionesMaterial": ["Tela", "Papel", "Plástico", "Madera", "Metal", "Flor Natural", "Flor Artificial", "Cinta"]
  },
  {
    "categoriaNombre": "Display",
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Material", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "DimensionesCapacidad", "FormaTipo", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Pieza", "Juego/Set", "Unidad"],
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Unidad"],
    "opcionesMaterial": ["Vidrio", "Plástico", "Acrílico", "Metal", "Madera", "Cartón", "Cerámica"]
  },
  {
    "categoriaNombre": "Mobiliario",
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "UnidadMedidaBase", "Material", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "Dimensiones", "Estilo", "Capacidad", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Pieza", "Set", "Juego"],
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Juego", "Unidad"],
    "opcionesMaterial": ["Madera", "Metal", "Plástico", "Tela", "Cristal"]
  },
  {
    "categoriaNombre": "Papelería",
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "Gramaje", "TipoPapel", "Dimensiones", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Paquete", "Hoja", "Rollo", "Caja", "Unidad"],
    "opcionesUnidadMedidaBase": ["Hoja", "Paquete", "Unidad", "Pliego", "Metro"],
    "opcionesMaterial": ["Papel Couché", "Papel Bond", "Cartulina Opalina", "Papel Adhesivo", "Vinil"]
  },
  {
    "categoriaNombre": "Servicios",
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "UnidadMedidaBase", "DiasAnticipacionCompra"],
    "camposOpcionales": ["DescripcionAdicionalInterna", "NivelExperienciaRequerido"],
    "opcionesPresentacion": ["Por Hora", "Por Proyecto", "Por Jornada", "Paquete de Horas"],
    "opcionesUnidadMedidaBase": ["Hora", "Servicio", "Jornada", "Unidad", "Proyecto"],
    "opcionesMaterial": []
  }
]

@api_bp.route('/product-categories-config', methods=['GET'])
def get_product_categories_config():
    db = SessionLocal()
    config_para_sheets = []
    try:
        # Iterar sobre la lista predefinida de nombres de categorías principales
        for nombre_cat_principal_predefinida in PREDEFINED_MAIN_CATEGORIES_NAMES:
            
            # Intentar encontrar esta categoría principal en la BD para obtener su ID y luego sus subcategorías
            cat_db_principal = db.query(Categoria)\
                                 .filter(Categoria.nombre_categoria == nombre_cat_principal_predefinida,
                                         Categoria.id_categoria_padre == None)\
                                 .first()

            s1_list_for_api = []
            if cat_db_principal:
                # Si la categoría principal existe en la BD, buscar sus S1
                print(f"API INFO: Procesando Categoría Principal de BD: {cat_db_principal.nombre_categoria} (ID: {cat_db_principal.id_categoria})")
                subcategorias_nivel1_db = db.query(Subcategoria)\
                                            .filter(Subcategoria.id_categoria_contenedora == cat_db_principal.id_categoria,
                                                    Subcategoria.id_subcategoria_padre == None)\
                                            .order_by(Subcategoria.nombre_subcategoria)\
                                            .all()
                
                for s1_db_obj in subcategorias_nivel1_db:
                    s2_list_for_api = []
                    subcategorias_nivel2_db = db.query(Subcategoria.nombre_subcategoria)\
                                                .filter(Subcategoria.id_subcategoria_padre == s1_db_obj.id_subcategoria)\
                                                .order_by(Subcategoria.nombre_subcategoria)\
                                                .all()
                    s2_list_for_api = [s2[0] for s2 in subcategorias_nivel2_db]
                    
                    s1_list_for_api.append({
                        "nombreS1": s1_db_obj.nombre_subcategoria,
                        "subcategoriasNivel2": s2_list_for_api
                    })
            else:
                # Si la categoría principal predefinida no está en la BD, se incluirá en la respuesta
                # pero su lista de subcategoriasNivel1 estará vacía.
                print(f"API INFO: Categoría Principal Predefinida '{nombre_cat_principal_predefinida}' no encontrada en BD. Se incluirá sin subcategorías S1/S2 de BD.")

            # Obtener la configuración detallada (camposRequeridos, etc.) de la estructura hardcodeada
            config_detallada_hc = next(
                (item for item in DETAILED_CATEGORY_CONFIG_DATA if item["categoriaNombre"] == nombre_cat_principal_predefinida), 
                {} 
            )
            
            config_cat_api = {
                "categoriaPrincipalNombre": nombre_cat_principal_predefinida, # Usar el nombre predefinido
                "subcategoriasNivel1": s1_list_for_api, # Esta lista estará vacía si la cat principal no está en BD o no tiene S1
                "camposRequeridos": config_detallada_hc.get("camposRequeridos", []),
                "camposOpcionales": config_detallada_hc.get("camposOpcionales", []),
                "opcionesPresentacion": config_detallada_hc.get("opcionesPresentacion", []),
                "opcionesUnidadMedidaBase": config_detallada_hc.get("opcionesUnidadMedidaBase", []),
                "opcionesMaterial": config_detallada_hc.get("opcionesMaterial", []),
                "opcionesModalidadServicio": config_detallada_hc.get("opcionesModalidadServicio", [])
            }
            config_para_sheets.append(config_cat_api)
            
        print(f"API DEBUG: Configuración final a enviar (longitud): {len(config_para_sheets)}")
        return jsonify(config_para_sheets)

    except Exception as e:
        print(f"ERROR en API /product-categories-config: {str(e)}")
        import traceback
        traceback.print_exc() 
        return jsonify({"error": f"Error interno del servidor al obtener categorías: {str(e)}"}), 500
    finally:
        if db.is_active:
            db.close()
