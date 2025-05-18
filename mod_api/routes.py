# /mod_api/routes.py
from flask import jsonify
from sqlalchemy.orm import Session, selectinload # Asegúrate de tener selectinload
from . import api_bp
from database import SessionLocal
from models import Categoria, Subcategoria

# Estructura de configuración detallada.
# Los "categoriaNombre" DEBEN coincidir con los nombres de CategoriaPrincipalProducto en tu BD.
# Los campos como "camposRequeridos", "opcionesPresentacion", etc., se usarán de aquí.
# Las "subcategoriasPermitidas" de esta lista ya NO se usarán para S1, se tomarán de la BD.
DETAILED_CATEGORY_CONFIG_DATA = [
  {
    "categoriaNombre": "Comestibles", # Coincide con tu CategoriaPrincipalProducto
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Sabor", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Bolsa", "Caja", "Bote", "Pieza", "Paquete", "A Granel", "Kg", "g", "Litro", "ml"],
    "opcionesUnidadMedidaBase": ["Pieza", "Paquete", "kg", "g", "Litro", "ml", "Porción"],
    "opcionesMaterial": []
  },
  {
    "categoriaNombre": "Art. Fiesta", # Nueva categoría principal
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Color", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Tamano", "Material", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Pieza", "Paquete", "Set", "Bolsa"],
    "opcionesUnidadMedidaBase": ["Pieza", "Paquete", "Set", "Unidad"],
    "opcionesMaterial": ["Látex", "Metálico/Foil", "Plástico", "Papel", "Cartón"]
  },
  {
    "categoriaNombre": "Material Deco", # Nueva categoría principal
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Color", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Dimensiones", "Material", "TemaEstilo", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Pieza", "Juego/Set", "Rollo", "Metro", "Paquete", "Unidad"],
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Rollo", "m", "cm", "Unidad", "g", "kg"],
    "opcionesMaterial": ["Tela", "Papel", "Plástico", "Madera", "Metal", "Flor Natural", "Flor Artificial", "Cinta"]
  },
  {
    "categoriaNombre": "Display", # Coincide con tu CategoriaPrincipalProducto
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "Material", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "DimensionesCapacidad", "FormaTipo", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Pieza", "Juego/Set", "Unidad"],
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Unidad"],
    "opcionesMaterial": ["Vidrio", "Plástico", "Acrílico", "Metal", "Madera", "Cartón", "Cerámica"]
  },
  {
    "categoriaNombre": "Mobiliario", # Nueva categoría principal
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "UnidadMedidaBase", "Material", "DiasAnticipacionCompra"], # Presentación puede no aplicar tanto
    "camposOpcionales": ["Color", "Dimensiones", "Estilo", "Capacidad", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Pieza", "Set", "Juego"], # Si aplica
    "opcionesUnidadMedidaBase": ["Pieza", "Set", "Juego", "Unidad"],
    "opcionesMaterial": ["Madera", "Metal", "Plástico", "Tela", "Cristal"]
  },
  {
    "categoriaNombre": "Papelería", # Nueva categoría principal
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "PresentacionCompraEstandar", "CantidadEnPresentacionCompraEstandar", "UnidadMedidaBase", "DiasAnticipacionCompra"],
    "camposOpcionales": ["Color", "Gramaje", "TipoPapel", "Dimensiones", "DescripcionAdicionalInterna", "MarcaProveedorSugerido"],
    "opcionesPresentacion": ["Paquete", "Hoja", "Rollo", "Caja", "Unidad"],
    "opcionesUnidadMedidaBase": ["Hoja", "Paquete", "Unidad", "Pliego", "Metro"],
    "opcionesMaterial": ["Papel Couché", "Papel Bond", "Cartulina Opalina", "Papel Adhesivo", "Vinil"]
  },
  {
    "categoriaNombre": "Servicios", # Coincide con tu CategoriaPrincipalProducto (para servicios internos)
    "camposRequeridos": ["SubcategoriaEspecificaNivel2", "NombreProducto", "UnidadMedidaBase", "DiasAnticipacionCompra"], # "Presentación" puede ser "N/A" o "Por Proyecto/Hora"
    "camposOpcionales": ["DescripcionAdicionalInterna", "NivelExperienciaRequerido"],
    "opcionesPresentacion": ["Por Hora", "Por Proyecto", "Por Jornada", "Paquete de Horas"],
    "opcionesUnidadMedidaBase": ["Hora", "Servicio", "Jornada", "Unidad", "Proyecto"],
    "opcionesMaterial": [] # Generalmente no aplica
  }
]

@api_bp.route('/product-categories-config', methods=['GET'])
def get_product_categories_config():
    db = SessionLocal()
    try:
        # Obtener las Categorías Principales (Nivel 0) de la BD
        # Estas deben coincidir con los "categoriaNombre" en DETAILED_CATEGORY_CONFIG_DATA
        categorias_principales_db = db.query(Categoria)\
                                   .filter(Categoria.id_categoria_padre == None)\
                                   .order_by(Categoria.nombre_categoria)\
                                   .all()
        
        config_para_sheets = []
        for cat_db_principal in categorias_principales_db: # Ej: "Comestibles"
            
            # Buscar la configuración detallada hardcodeada (para camposRequeridos, opcionesPresentacion, etc.)
            # basada en el nombre de la categoría principal de la BD.
            config_detallada_hc = next(
                (item for item in DETAILED_CATEGORY_CONFIG_DATA if item["categoriaNombre"] == cat_db_principal.nombre_categoria), 
                {} # Usar un diccionario vacío si no se encuentra para evitar errores y usar valores por defecto vacíos.
            )

            s1_list_for_api = []
            # Obtener Subcategorías Nivel 1 (S1) para esta CategoriaPrincipal (cat_db_principal)
            # Estas son las Subcategoria que tienen como id_categoria_contenedora el id de cat_db_principal
            # Y que NO tienen un id_subcategoria_padre (son el primer nivel de subcategoría)
            subcategorias_nivel1_db = db.query(Subcategoria)\
                                        .filter(Subcategoria.id_categoria_contenedora == cat_db_principal.id_categoria,
                                                Subcategoria.id_subcategoria_padre == None)\
                                        .order_by(Subcategoria.nombre_subcategoria)\
                                        .all()

            for s1_db_obj in subcategorias_nivel1_db: # Ej: S1 "Dulces"
                s2_list_for_api = []
                # Obtener Subcategorías Nivel 2 (S2) para esta Subcategoría Nivel 1 (s1_db_obj)
                # Estas son las Subcategoria que tienen como id_subcategoria_padre el id de s1_db_obj
                subcategorias_nivel2_db = db.query(Subcategoria.nombre_subcategoria)\
                                            .filter(Subcategoria.id_subcategoria_padre == s1_db_obj.id_subcategoria)\
                                            .order_by(Subcategoria.nombre_subcategoria)\
                                            .all()
                s2_list_for_api = [s2[0] for s2 in subcategorias_nivel2_db] # Lista de nombres de S2, ej: ["Gomitas", "Chocolates"]
                
                s1_list_for_api.append({
                    "nombreS1": s1_db_obj.nombre_subcategoria,
                    # "idS1": s1_db_obj.id_subcategoria, # Opcional: si AppScript lo necesita para algo más que el nombre.
                    "subcategoriasNivel2": s2_list_for_api # Lista de nombres de S2
                })
            
            # Construir el objeto de configuración para esta categoría principal
            config_cat_api = {
                "categoriaPrincipalNombre": cat_db_principal.nombre_categoria,
                # "idCategoriaPrincipal": cat_db_principal.id_categoria, # Opcional, si AppScript lo necesita.
                "subcategoriasNivel1": s1_list_for_api, # Lista de objetos S1, cada uno con sus S2.
                
                # Tomar los campos de configuración detallada del objeto hardcodeado correspondiente.
                "camposRequeridos": config_detallada_hc.get("camposRequeridos", []),
                "camposOpcionales": config_detallada_hc.get("camposOpcionales", []),
                "opcionesPresentacion": config_detallada_hc.get("opcionesPresentacion", []),
                "opcionesUnidadMedidaBase": config_detallada_hc.get("opcionesUnidadMedidaBase", []),
                "opcionesMaterial": config_detallada_hc.get("opcionesMaterial", []),
                "opcionesModalidadServicio": config_detallada_hc.get("opcionesModalidadServicio", []) # Si aplica
            }
            config_para_sheets.append(config_cat_api)
            
        return jsonify(config_para_sheets)

    except Exception as e:
        print(f"Error en API /product-categories-config: {str(e)}")
        import traceback
        traceback.print_exc() # Imprime el stack trace completo en la consola del servidor para depuración.
        return jsonify({"error": f"Error interno del servidor al obtener categorías: {str(e)}"}), 500
    finally:
        if db.is_active:
            db.close()
