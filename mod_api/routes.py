# /mod_api/routes.py
from flask import jsonify
from sqlalchemy.orm import Session, selectinload
from . import api_bp
from database import SessionLocal
from models import Categoria, Subcategoria

PREDEFINED_MAIN_CATEGORIES_NAMES = [
    "Comestibles", "Art. Fiesta", "Material Deco", "Display",
    "Mobiliario", "Papelería", "Servicios"
]

# Estructura de configuración detallada.
# REVISADA v2 para que camposRequeridos/Opcionales y listas de opciones sean más coherentes
# y para reflejar mejor la distinción entre UnidadMedidaBase y PresentacionCompraEstandar.
DETAILED_CATEGORY_CONFIG_DATA = [
  {
    "categoriaNombre": "Comestibles",
    "camposRequeridos": ["SubcategoriaProductoNivel1", "SubcategoriaProductoNivel2", "NombreProducto", "UnidadMedidaBase", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "Sabor", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "Marca", "DescripcionAdicionalInterna", "EsIndivisible"],
    "opcionesPresentacion": ["Bolsa", "Caja", "Bote", "Paquete", "Display (ej. con X piezas)", "Kg Granel", "Litro Granel", "Atado", "Charola", "Unidad Suelta (si se compra así)"],
    "opcionesUnidadMedidaBase": ["Pieza", "g", "ml", "Porción", "Unidad"], # Unidad fundamental del ítem
    "opcionesMaterial": []
  },
  {
    "categoriaNombre": "Art. Fiesta",
    "camposRequeridos": ["SubcategoriaProductoNivel1", "SubcategoriaProductoNivel2", "NombreProducto", "UnidadMedidaBase", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "Color", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Tamano", "Material", "TemaEstilo", "Marca", "DescripcionAdicionalInterna", "EsIndivisible"],
    "opcionesPresentacion": ["Pieza", "Paquete", "Set", "Bolsa", "Rollo", "Caja"],
    "opcionesUnidadMedidaBase": ["Pieza", "Unidad", "Metro", "Set"],
    "opcionesMaterial": ["Látex", "Metálico/Foil", "Plástico", "Papel", "Cartón", "Tela", "Confeti"]
  },
  {
    "categoriaNombre": "Material Deco",
    "camposRequeridos": ["SubcategoriaProductoNivel1", "SubcategoriaProductoNivel2", "NombreProducto", "UnidadMedidaBase", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "DimensionesCapacidad", "Material", "TemaEstilo", "FormaTipo", "Marca", "DescripcionAdicionalInterna", "EsIndivisible"],
    "opcionesPresentacion": ["Pieza", "Juego/Set", "Rollo", "Metro Lineal", "Paquete", "Atado", "Vara", "Pliego", "Bolsa", "Caja"],
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Metro", "cm", "Unidad", "g", "kg", "Vara", "Pliego"],
    "opcionesMaterial": ["Tela", "Papel", "Plástico", "Madera", "Metal", "Flor Natural", "Flor Artificial", "Cinta", "Alambre", "Espuma Floral", "Vidrio (adornos)", "Vela"]
  },
  {
    "categoriaNombre": "Display",
    "camposRequeridos": ["SubcategoriaProductoNivel1", "SubcategoriaProductoNivel2", "NombreProducto", "UnidadMedidaBase", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "Material", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "DimensionesCapacidad", "FormaTipo", "Marca", "DescripcionAdicionalInterna", "EsIndivisible"],
    "opcionesPresentacion": ["Pieza", "Juego/Set", "Caja (si vienen múltiples)", "Paquete"],
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Unidad"], # Generalmente se compran como unidades o sets
    "opcionesMaterial": ["Vidrio", "Plástico", "Acrílico", "Metal", "Madera", "Cartón", "Cerámica", "Bambú"]
  },
  {
    "categoriaNombre": "Mobiliario",
    "camposRequeridos": ["SubcategoriaProductoNivel1", "SubcategoriaProductoNivel2", "NombreProducto", "UnidadMedidaBase", "Material", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "DimensionesCapacidad", "Estilo", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "Marca", "DescripcionAdicionalInterna", "Peso", "EsIndivisible"],
    "opcionesPresentacion": ["Pieza", "Set", "Juego (ej. sala lounge)"], # Cómo se adquiere
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Unidad"], # Cómo se cuenta para inventario/alquiler
    "opcionesMaterial": ["Madera", "Metal", "Plástico", "Tela", "Cristal", "Ratán", "Acrílico", "Mármol"]
  },
  {
    "categoriaNombre": "Papelería",
    "camposRequeridos": ["SubcategoriaProductoNivel1", "SubcategoriaProductoNivel2", "NombreProducto", "UnidadMedidaBase", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "Tamano", "Material", "DimensionesCapacidad", "TemaEstilo", "Marca", "DescripcionAdicionalInterna", "EsIndivisible"],
    "opcionesPresentacion": ["Paquete", "Hoja Individual", "Rollo", "Caja", "Resma", "Block"],
    "opcionesUnidadMedidaBase": ["Hoja", "Unidad", "Pliego", "Metro", "Pieza"],
    "opcionesMaterial": ["Papel Couché", "Papel Bond", "Cartulina Opalina", "Papel Adhesivo", "Vinil", "Papel Reciclado", "Papel Texturizado", "Cartón", "Acetato"]
  },
  {
    "categoriaNombre": "Servicios",
    "camposRequeridos": ["SubcategoriaProductoNivel1", "SubcategoriaProductoNivel2", "NombreProducto", "UnidadMedidaBase", "DiasAnticipacionCompra"],
    "camposOpcionales": ["DescripcionAdicionalInterna", "NivelExperienciaRequerido", "TarifaReferenciaInterna", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "EsIndivisible"], # Presentación podría ser "Paquete de X Horas"
    "opcionesPresentacion": ["Por Hora", "Por Jornada", "Por Proyecto Base", "Unidad de Servicio", "Paquete de Horas", "Contrato"],
    "opcionesUnidadMedidaBase": ["Hora", "Jornada", "Servicio", "Unidad", "Proyecto"],
    "opcionesMaterial": []
  }
]

@api_bp.route('/product-categories-config', methods=['GET'])
def get_product_categories_config():
    db = SessionLocal()
    config_para_sheets = []
    try:
        for nombre_cat_principal_predefinida in PREDEFINED_MAIN_CATEGORIES_NAMES:
            cat_db_principal = db.query(Categoria)\
                                 .filter(Categoria.nombre_categoria == nombre_cat_principal_predefinida,
                                         Categoria.id_categoria_padre == None)\
                                 .first()
            s1_list_for_api = []
            if cat_db_principal:
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

            config_detallada_hc = next(
                (item for item in DETAILED_CATEGORY_CONFIG_DATA if item["categoriaNombre"] == nombre_cat_principal_predefinida), 
                {} 
            )
            
            config_cat_api = {
                "categoriaPrincipalNombre": nombre_cat_principal_predefinida,
                "subcategoriasNivel1": s1_list_for_api,
                "camposRequeridos": config_detallada_hc.get("camposRequeridos", []),
                "camposOpcionales": config_detallada_hc.get("camposOpcionales", []),
                "opcionesPresentacion": config_detallada_hc.get("opcionesPresentacion", []),
                "opcionesUnidadMedidaBase": config_detallada_hc.get("opcionesUnidadMedidaBase", []),
                "opcionesMaterial": config_detallada_hc.get("opcionesMaterial", []),
                "opcionesModalidadServicio": config_detallada_hc.get("opcionesModalidadServicio", [])
            }
            config_para_sheets.append(config_cat_api)
            
        return jsonify(config_para_sheets)

    except Exception as e:
        print(f"ERROR en API /product-categories-config: {str(e)}")
        import traceback
        traceback.print_exc() 
        return jsonify({"error": f"Error interno del servidor al obtener categorías: {str(e)}"}), 500
    finally:
        if db.is_active:
            db.close()
