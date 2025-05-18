# /mod_productos/routes.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy.orm import Session, joinedload, selectinload, aliased, contains_eager
from sqlalchemy import asc, desc, or_, and_, func as sqlfunc, inspect
from decimal import Decimal

from . import productos_bp
from database import SessionLocal 
from models import Producto, Categoria, Subcategoria 
from utils_carga import ( 
    parsear_y_validar_csv_productos, guardar_productos_en_bd, construir_descripcion_completa,
    generar_siguiente_sku, get_or_create_categoria_principal # Asegúrate de importar esta función
)

# Lista predefinida de las 7 Categorías Principales para los formularios
PREDEFINED_MAIN_CATEGORIES_NAMES_FOR_FORM = [
    "Comestibles", "Art. Fiesta", "Material Deco", "Display",
    "Mobiliario", "Papelería", "Servicios"
]

def _build_categorias_jerarquia(db: Session):
    """
    Construye la estructura jerárquica de categorías.
    Asegura que las PREDEFINED_MAIN_CATEGORIES_NAMES_FOR_FORM siempre estén presentes.
    """
    categorias_jerarquia_data = {}
    
    for nombre_cat_principal_predefinida in PREDEFINED_MAIN_CATEGORIES_NAMES_FOR_FORM:
        # Intenta encontrar la categoría principal en la BD
        cat_db_principal = db.query(Categoria)\
                             .filter(Categoria.nombre_categoria == nombre_cat_principal_predefinida,
                                     Categoria.id_categoria_padre == None)\
                             .first()
        
        s1_dict = {}
        # La clave para el diccionario de la plantilla será el ID si la categoría existe en la BD,
        # o el nombre de la categoría predefinida si aún no existe (para que aparezca en el desplegable).
        # El JavaScript en la plantilla y la lógica de guardado en el backend (usando get_or_create)
        # manejarán si se envía un ID o un nombre.
        cat_id_for_template = str(cat_db_principal.id_categoria) if cat_db_principal else nombre_cat_principal_predefinida

        if cat_db_principal:
            # Si la categoría principal existe en la BD, buscar sus S1
            subcategorias_s1_db = db.query(Subcategoria).filter(
                Subcategoria.id_categoria_contenedora == cat_db_principal.id_categoria, # S1 pertenece a esta Cat Principal
                Subcategoria.id_subcategoria_padre == None # S1 no tiene padre S1 (es de primer nivel)
            ).order_by(Subcategoria.nombre_subcategoria).all()
            for s1 in subcategorias_s1_db:
                s2_dict = {}
                # Buscar S2 para esta S1
                subcategorias_s2_db = db.query(Subcategoria).filter(
                    Subcategoria.id_subcategoria_padre == s1.id_subcategoria # S2 es hija de esta S1
                ).order_by(Subcategoria.nombre_subcategoria).all()
                for s2 in subcategorias_s2_db:
                    s2_dict[str(s2.id_subcategoria)] = s2.nombre_subcategoria
                s1_dict[str(s1.id_subcategoria)] = {"nombre": s1.nombre_subcategoria, "subcategorias_nivel2": s2_dict}
        
        categorias_jerarquia_data[cat_id_for_template] = {
            "nombre": nombre_cat_principal_predefinida, # Siempre usa el nombre predefinido para mostrar en el desplegable
            "subcategorias_nivel1": s1_dict # Esta lista estará vacía si la cat principal no está en BD o no tiene S1
        }
    return categorias_jerarquia_data


def get_producto_by_id_for_edit(db: Session, id_producto: int) -> Producto | None:
    # Alias para las tablas Categoria y Subcategoria para evitar conflictos en joins complejos
    CatPrincAlias = aliased(Categoria, name="cat_princ_edit_alias")
    SubcatEspAlias = aliased(Subcategoria, name="sub_esp_edit_alias") # Esta sería S2
    CatDeSubcatAlias = aliased(Categoria, name="cat_de_sub_edit_alias") # Categoría contenedora de S1 (si S1 existe)
    SubcatPadreS1Alias = aliased(Subcategoria, name="sub_padre_s1_alias") # Esta sería S1, padre de S2

    # Cargar el producto con sus relaciones de categoría
    # Usamos joinedload y contains_eager para cargar eficientemente las relaciones
    return db.query(Producto)\
        .outerjoin(CatPrincAlias, Producto.id_categoria_principal_producto == CatPrincAlias.id_categoria)\
        .outerjoin(SubcatEspAlias, Producto.id_subcategoria_especifica_producto == SubcatEspAlias.id_subcategoria)\
        .outerjoin(SubcatPadreS1Alias, SubcatEspAlias.id_subcategoria_padre == SubcatPadreS1Alias.id_subcategoria) \
        .outerjoin(CatDeSubcatAlias, SubcatPadreS1Alias.id_categoria_contenedora == CatDeSubcatAlias.id_categoria)\
        .options(
            contains_eager(Producto.categoria_principal_producto, alias=CatPrincAlias), # Carga la Cat Principal directa del producto
            contains_eager(Producto.subcategoria_especifica_producto, alias=SubcatEspAlias) # Carga S2
                .contains_eager(Subcategoria.subcategoria_padre_ref, alias=SubcatPadreS1Alias) # Carga S1 (padre de S2)
                    .contains_eager(Subcategoria.categoria_contenedora, alias=CatDeSubcatAlias) # Carga la Cat Principal de S1
        )\
        .filter(Producto.id_producto == id_producto).first()

def update_producto_db(db: Session, id_producto: int, datos_actualizacion: dict) -> Producto | None:
    # Obtener el producto a editar con sus relaciones cargadas
    producto_db = get_producto_by_id_for_edit(db, id_producto)
    if not producto_db:
        return None

    # Lista de campos que se pueden actualizar desde el formulario
    campos_actualizables = [
        "nombre_producto", "id_categoria_principal_producto", "id_subcategoria_especifica_producto",
        "descripcion_adicional", "presentacion_compra", "cantidad_en_presentacion_compra",
        "unidad_medida_base", "es_indivisible", "marca", "sabor", "color", "tamano_pulgadas", "material", 
        "dimensiones_capacidad", "tema_estilo", "modalidad_servicio_directo", "forma_tipo",
        "dias_anticipacion_compra_proveedor", "activo", "modelo_sku_proveedor"
    ]
    cambios_hechos = False
    for campo in campos_actualizables:
        if campo in datos_actualizacion:
            valor_actualizar = datos_actualizacion[campo]
            
            # Conversión y validación de tipos de datos
            if campo == "activo" or campo == "es_indivisible": 
                valor_actualizar = True if valor_actualizar == 'on' or valor_actualizar is True else False
            elif campo in ["id_categoria_principal_producto", "id_subcategoria_especifica_producto", "dias_anticipacion_compra_proveedor"]:
                # Manejar el caso donde el valor podría ser un nombre temporal (ej. "Comestibles")
                # o un ID numérico. La conversión a int solo si es numérico.
                if isinstance(valor_actualizar, str) and not valor_actualizar.isdigit():
                    # Si es un nombre (como los predefinidos que aún no están en BD),
                    # la lógica de get_or_create en el guardado se encargará.
                    # Aquí, para la actualización directa del ID, necesitaríamos el ID real.
                    # Si se espera que el formulario envíe IDs reales para categorías existentes,
                    # y nombres para nuevas, la lógica de guardado debe manejarlo.
                    # Por ahora, si no es un dígito y no es vacío, lo dejamos como está para que
                    # la lógica de guardado (si se adapta) o get_or_create lo maneje.
                    # O, si el formulario SIEMPRE debe enviar IDs, esto sería un error.
                    # Para update_producto_db, esperamos IDs.
                    if valor_actualizar == '' or valor_actualizar is None:
                        valor_actualizar = None
                    else: # Si no es vacío y no es dígito, es un error para este campo de ID
                        print(f"Advertencia: Valor no numérico para campo ID {campo}: {valor_actualizar}. Se intentará convertir, pero podría fallar.")
                        try:
                            valor_actualizar = int(valor_actualizar) # Esto fallará si es un nombre
                        except ValueError:
                             print(f"Error: No se pudo convertir '{valor_actualizar}' a int para {campo}. Se omite la actualización de este campo.")
                             continue # Saltar este campo
                elif valor_actualizar == '' or valor_actualizar is None:
                    valor_actualizar = None
                else: # Es un dígito o convertible a dígito
                    try:
                        valor_actualizar = int(valor_actualizar)
                    except ValueError:
                        print(f"Advertencia: Valor no entero para {campo}: {valor_actualizar}. Se ignora.")
                        continue
            elif campo == "cantidad_en_presentacion_compra":
                if valor_actualizar == '' or valor_actualizar is None:
                    valor_actualizar = None
                else:
                    try:
                        valor_actualizar = Decimal(str(valor_actualizar))
                    except:
                        print(f"Advertencia: Valor no decimal para {campo}: {valor_actualizar}. Se ignora.")
                        continue
            
            # Solo actualizar si el valor es diferente para evitar commits innecesarios
            if getattr(producto_db, campo) != valor_actualizar:
                setattr(producto_db, campo, valor_actualizar)
                cambios_hechos = True
    
    if cambios_hechos:
        # Regenerar descripción completa si hubo cambios
        datos_para_desc = {c.key: getattr(producto_db, c.key) for c in inspect(producto_db).mapper.column_attrs if hasattr(producto_db, c.key)}
        
        # Para la descripción, necesitamos los nombres de las categorías.
        # Refrescar las relaciones si los IDs cambiaron antes de acceder a los nombres.
        db.refresh(producto_db, ['categoria_principal_producto', 'subcategoria_especifica_producto'])
        if producto_db.subcategoria_especifica_producto:
            db.refresh(producto_db.subcategoria_especifica_producto, ['subcategoria_padre_ref'])


        nombre_cat_p_desc = None
        if producto_db.id_categoria_principal_producto:
            # Si el ID es un nombre temporal (no debería pasar aquí si se guardó un ID)
            # Pero si se permite guardar nombres temporales, esta lógica es necesaria.
            # Asumiendo que id_categoria_principal_producto ahora es un ID real.
            if producto_db.categoria_principal_producto:
                nombre_cat_p_desc = producto_db.categoria_principal_producto.nombre_categoria
        datos_para_desc['nombre_categoria_principal'] = nombre_cat_p_desc

        nombre_s1_desc = None
        nombre_s2_desc = None
        if producto_db.subcategoria_especifica_producto: # S2
            nombre_s2_desc = producto_db.subcategoria_especifica_producto.nombre_subcategoria
            if producto_db.subcategoria_especifica_producto.subcategoria_padre_ref: # S1
                 nombre_s1_desc = producto_db.subcategoria_especifica_producto.subcategoria_padre_ref.nombre_subcategoria
        datos_para_desc['nombre_subcategoria_nivel1'] = nombre_s1_desc
        datos_para_desc['nombre_subcategoria_especifica'] = nombre_s2_desc # Este es S2
        
        producto_db.descripcion_completa_generada = construir_descripcion_completa(datos_para_desc)
    try:
        db.commit()
        db.refresh(producto_db) # Refrescar el objeto después del commit
        return producto_db
    except Exception as e:
        db.rollback()
        print(f"Error al actualizar producto ID {id_producto}: {e}")
        raise e

def _construir_query_productos_filtrados(db_session: Session, args: dict):
    # ... (código existente sin cambios) ...
    search_query = args.get('q', '').strip()
    categoria_principal_id_filter = args.get('id_categoria_principal_producto', type=int)
    subcategoria_especifica_id_filter = args.get('id_subcategoria_especifica_producto', type=int) # Este es S2
    sabor_filter = args.get('sabor', '').strip()
    color_filter = args.get('color', '').strip()
    material_filter = args.get('material', '').strip()
    sort_by_param = args.get('sort_by', 'nombre')
    sort_order_param = args.get('sort_order', 'asc')

    CatPrincAlias = aliased(Categoria, name="cat_princ_alias_bp")
    SubcatEspAlias = aliased(Subcategoria, name="sub_esp_alias_bp") # S2
    SubcatPadreAlias = aliased(Subcategoria, name="sub_padre_alias_bp") # S1 (padre de S2)
    CatDeS1Alias = aliased(Categoria, name="cat_de_s1_alias_filter_bp") # Cat Principal de S1

    query = db_session.query(Producto)\
        .outerjoin(CatPrincAlias, Producto.id_categoria_principal_producto == CatPrincAlias.id_categoria)\
        .outerjoin(SubcatEspAlias, Producto.id_subcategoria_especifica_producto == SubcatEspAlias.id_subcategoria)\
        .outerjoin(SubcatPadreAlias, SubcatEspAlias.id_subcategoria_padre == SubcatPadreAlias.id_subcategoria)\
        .outerjoin(CatDeS1Alias, SubcatPadreAlias.id_categoria_contenedora == CatDeS1Alias.id_categoria)

    query = query.options(
        contains_eager(Producto.categoria_principal_producto, alias=CatPrincAlias), # Cat Principal directa
        contains_eager(Producto.subcategoria_especifica_producto, alias=SubcatEspAlias) # S2
            .contains_eager(Subcategoria.subcategoria_padre_ref, alias=SubcatPadreAlias) # S1
                .contains_eager(Subcategoria.categoria_contenedora, alias=CatDeS1Alias) # Cat Principal de S1
    )
    
    sortable_columns = {
        "id": Producto.id_producto, 
        "sku": Producto.sku, 
        "nombre": Producto.nombre_producto,
        "categoria_principal": sqlfunc.coalesce(CatPrincAlias.nombre_categoria, CatDeS1Alias.nombre_categoria),
        "subcategoria_nivel1": SubcatPadreAlias.nombre_subcategoria, 
        "subcategoria_nivel2": SubcatEspAlias.nombre_subcategoria, 
        "presentacion_compra": Producto.presentacion_compra, 
        "activo": Producto.activo
    }
    column_to_sort_expression = sortable_columns.get(sort_by_param, Producto.nombre_producto)

    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(or_(Producto.nombre_producto.ilike(search_term), Producto.sku.ilike(search_term), Producto.descripcion_completa_generada.ilike(search_term)))
    
    if categoria_principal_id_filter:
        query = query.filter(or_(
            Producto.id_categoria_principal_producto == categoria_principal_id_filter, # Coincide con la CatP directa
            CatDeS1Alias.id_categoria == categoria_principal_id_filter # O coincide con la CatP de la S1
        ))
    
    # Si se filtra por subcategoria_especifica_id_filter, se asume que es el ID de la S2
    if subcategoria_especifica_id_filter: 
        query = query.filter(Producto.id_subcategoria_especifica_producto == subcategoria_especifica_id_filter)
    
    # Aquí podrías añadir un filtro para SubcategoriaNivel1 si lo implementas en el frontend
    # id_subcategoria_nivel1_filter = args.get('id_subcategoria_nivel1', type=int)
    # if id_subcategoria_nivel1_filter:
    #     query = query.filter(SubcatPadreAlias.id_subcategoria == id_subcategoria_nivel1_filter)

    if sabor_filter: query = query.filter(Producto.sabor.ilike(f"%{sabor_filter}%"))
    if color_filter: query = query.filter(Producto.color.ilike(f"%{color_filter}%"))
    if material_filter: query = query.filter(Producto.material.ilike(f"%{material_filter}%"))
    
    order_final_expression = desc(column_to_sort_expression) if sort_order_param == 'desc' else asc(column_to_sort_expression)
    query = query.order_by(order_final_expression, Producto.id_producto)
    
    return query, sort_by_param, sort_order_param

def obtener_info_precios_producto(db: Session, id_producto: int) -> dict:
    from models import DetalleCompra, EncabezadoCompra, Proveedor 
    info = {
        "precio_min": None, "proveedor_min": None, "disponibilidad_min": None,
        "precio_max": None, "proveedor_max": None, "disponibilidad_max": None
    }
    subq_ultima_compra_por_proveedor = db.query(
        DetalleCompra.id_encabezado_compra, EncabezadoCompra.id_proveedor, DetalleCompra.disponibilidad_proveedor,
        sqlfunc.row_number().over(partition_by=EncabezadoCompra.id_proveedor, order_by=desc(EncabezadoCompra.fecha_documento)).label('rn')
    ).join(EncabezadoCompra, DetalleCompra.id_encabezado_compra == EncabezadoCompra.id_encabezado_compra)\
    .filter(DetalleCompra.id_producto == id_producto).subquery()

    detalles_con_proveedor_y_disp = db.query(
        DetalleCompra.costo_unitario_compra, Proveedor.nombre_proveedor,
        subq_ultima_compra_por_proveedor.c.disponibilidad_proveedor.label("ultima_disponibilidad")
    ).select_from(DetalleCompra)\
    .join(EncabezadoCompra, DetalleCompra.id_encabezado_compra == EncabezadoCompra.id_encabezado_compra)\
    .join(Proveedor, EncabezadoCompra.id_proveedor == Proveedor.id_proveedor)\
    .outerjoin(subq_ultima_compra_por_proveedor, and_(
        EncabezadoCompra.id_proveedor == subq_ultima_compra_por_proveedor.c.id_proveedor,
        subq_ultima_compra_por_proveedor.c.rn == 1
    )).filter(DetalleCompra.id_producto == id_producto).all()

    if not detalles_con_proveedor_y_disp: return info
    min_entry = min(detalles_con_proveedor_y_disp, key=lambda x: x.costo_unitario_compra)
    info["precio_min"] = min_entry.costo_unitario_compra
    info["proveedor_min"] = min_entry.nombre_proveedor
    info["disponibilidad_min"] = min_entry.ultima_disponibilidad or "N/A"
    max_entry = max(detalles_con_proveedor_y_disp, key=lambda x: x.costo_unitario_compra)
    info["precio_max"] = max_entry.costo_unitario_compra
    info["proveedor_max"] = max_entry.nombre_proveedor
    info["disponibilidad_max"] = max_entry.ultima_disponibilidad or "N/A"
    return info

PORCENTAJE_AUMENTO_MENSUAL_EST = 0.005 

@productos_bp.route('/', methods=['GET'])
def vista_listar_productos():
    db_session = SessionLocal()
    try:
        query, sort_by_param, sort_order_param = _construir_query_productos_filtrados(db_session, request.args)
        productos_db_raw = query.all()
        productos_enriquecidos = []
        for prod in productos_db_raw:
            info_precios = obtener_info_precios_producto(db_session, prod.id_producto)
            prod.info_precios = info_precios
            productos_enriquecidos.append(prod)

        categorias_db = db_session.query(Categoria).filter(Categoria.id_categoria_padre == None).order_by(Categoria.nombre_categoria).all()
        subcategorias_db_para_filtro = db_session.query(Subcategoria).order_by(Subcategoria.nombre_subcategoria).all()
        
        sabores_db = [s[0] for s in db_session.query(Producto.sabor).distinct().filter(Producto.sabor != None, Producto.sabor != '').order_by(Producto.sabor).all()]
        colores_db = [c[0] for c in db_session.query(Producto.color).distinct().filter(Producto.color != None, Producto.color != '').order_by(Producto.color).all()]
        materiales_db = [m[0] for m in db_session.query(Producto.material).distinct().filter(Producto.material != None, Producto.material != '').order_by(Producto.material).all()]

        current_sort = {'by': sort_by_param, 'order': sort_order_param}
        current_filters = {
            'q': request.args.get('q', '').strip(),
            'id_categoria_principal_producto': request.args.get('id_categoria_principal_producto', type=int),
            'id_subcategoria_especifica_producto': request.args.get('id_subcategoria_especifica_producto', type=int),
            'sabor': request.args.get('sabor', '').strip(),
            'color': request.args.get('color', '').strip(),
            'material': request.args.get('material', '').strip()
        }
        sortable_columns_keys = ["id", "sku", "nombre", "categoria_principal", "subcategoria_nivel1", "subcategoria_nivel2", "presentacion_compra", "activo"]

        return render_template('listar_productos.html',
                               productos=productos_enriquecidos,
                               titulo_pagina="Listado de Productos Internos",
                               current_sort=current_sort,
                               sortable_column_keys=sortable_columns_keys,
                               categorias=categorias_db, 
                               subcategorias=subcategorias_db_para_filtro,
                               sabores=sabores_db, colores=colores_db, materiales=materiales_db,
                               current_filters=current_filters, request_args=request.args,
                               aumento_mensual_est=PORCENTAJE_AUMENTO_MENSUAL_EST)
    except Exception as e:
        print(f"Error al obtener productos: {e}")
        flash(f"Error al cargar la lista de productos: {str(e)}", "danger")
        return render_template('listar_productos.html', productos=[], titulo_pagina="Listado de Productos Internos",
                               current_sort={}, sortable_column_keys=[],
                               categorias=[], subcategorias=[], sabores=[], colores=[], materiales=[],
                               current_filters={}, request_args={}, aumento_mensual_est=PORCENTAJE_AUMENTO_MENSUAL_EST)
    finally:
        db_session.close()

@productos_bp.route('/api/filtrar', methods=['GET'])
def api_filtrar_productos():
    db_session = SessionLocal()
    try:
        query, sort_by_param, sort_order_param = _construir_query_productos_filtrados(db_session, request.args)
        productos_db_raw = query.all()
        productos_enriquecidos_api = []
        for prod in productos_db_raw:
            info_precios = obtener_info_precios_producto(db_session, prod.id_producto)
            prod.info_precios = info_precios
            productos_enriquecidos_api.append(prod)
        current_sort = {'by': sort_by_param, 'order': sort_order_param}
        sortable_columns_keys = ["id", "sku", "nombre", "categoria_principal", "subcategoria_nivel1", "subcategoria_nivel2", "presentacion_compra", "activo"]
        return render_template('_tabla_productos_parcial.html',
                               productos=productos_enriquecidos_api,
                               current_sort=current_sort, sortable_column_keys=sortable_columns_keys,
                               request_args=request.args, aumento_mensual_est=PORCENTAJE_AUMENTO_MENSUAL_EST)
    except Exception as e:
        print(f"Error en API filtrar productos: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()

@productos_bp.route('/api/buscar_por_descripcion', methods=['GET'])
def api_buscar_productos_por_descripcion():
    db = SessionLocal()
    try:
        term = request.args.get('term', '').strip()
        id_exacto = request.args.get('id_exacto', type=int)
        productos_encontrados = []
        if id_exacto:
            producto = db.query(Producto).get(id_exacto)
            if producto and producto.activo:
                productos_encontrados.append(producto)
        elif term and len(term) >= 2:
            productos_encontrados = db.query(Producto)\
                .filter(Producto.descripcion_completa_generada.ilike(f"%{term}%"))\
                .filter(Producto.activo == True).limit(10).all()
        else:
             return jsonify([])
        resultados = []
        for prod in productos_encontrados:
            resultados.append({
                "id": prod.id_producto, "descripcion": prod.descripcion_completa_generada,
                "nombre": prod.nombre_producto, "sku": prod.sku,
                "presentacion": prod.presentacion_compra or prod.unidad_medida_base or "Unidad",
                "unidad_medida_base": prod.unidad_medida_base
            })
        return jsonify(resultados)
    except Exception as e:
        print(f"Error en API buscar productos por descripción: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@productos_bp.route('/crear', methods=['GET', 'POST'])
def vista_crear_producto_unico():
    db = SessionLocal()
    request_form_data_repopulate = {} 
    categorias_jerarquia_data = {} 

    try:
        # Construir la jerarquía de categorías para los desplegables SIEMPRE
        categorias_jerarquia_data = _build_categorias_jerarquia(db)

        if request.method == 'POST':
            request_form_data_repopulate = request.form.to_dict()
            
            nombre_producto = request.form.get('nombre_producto', '').strip()
            id_categoria_principal_form_val = request.form.get('id_categoria_principal_producto')
            id_subcategoria_nivel2_str = request.form.get('id_subcategoria_especifica_producto')

            errores_validacion = []
            if not nombre_producto:
                errores_validacion.append("Nombre del producto es obligatorio.")
            if not id_categoria_principal_form_val:
                errores_validacion.append("Categoría Principal es obligatoria.")
            if not id_subcategoria_nivel2_str:
                errores_validacion.append("Subcategoría Nivel 2 (Específica) es obligatoria.")

            cat_p_obj_para_sku = None
            id_cat_principal_real = None
            nombre_cat_principal_seleccionada = request.form.get('nombre_categoria_principal_seleccionada')

            if nombre_cat_principal_seleccionada: # Nombre de la categoría principal del campo oculto
                cat_p_obj_para_sku = get_or_create_categoria_principal(db, nombre_cat_principal_seleccionada)
                if cat_p_obj_para_sku:
                    id_cat_principal_real = cat_p_obj_para_sku.id_categoria
                else: # No debería pasar si get_or_create funciona bien y siempre devuelve un objeto o None
                    errores_validacion.append(f"No se pudo obtener o crear la Categoría Principal '{nombre_cat_principal_seleccionada}'.")
            elif id_categoria_principal_form_val and id_categoria_principal_form_val.isdigit(): # Si se envió un ID
                cat_p_obj_para_sku = db.query(Categoria).get(int(id_categoria_principal_form_val))
                if cat_p_obj_para_sku:
                    id_cat_principal_real = cat_p_obj_para_sku.id_categoria
                    nombre_cat_principal_seleccionada = cat_p_obj_para_sku.nombre_categoria # Asegurar que tengamos el nombre
                else:
                    errores_validacion.append("Categoría Principal (por ID) no encontrada.")
            else: # Si no hay nombre ni ID válido
                 errores_validacion.append("Selección de Categoría Principal inválida.")


            id_s2_obj = None
            if id_subcategoria_nivel2_str and id_subcategoria_nivel2_str.isdigit():
                id_s2_obj = db.query(Subcategoria).get(int(id_subcategoria_nivel2_str))
                if not id_s2_obj:
                    errores_validacion.append("Subcategoría Nivel 2 seleccionada no es válida.")
            elif id_subcategoria_nivel2_str:
                 errores_validacion.append("ID de Subcategoría Nivel 2 inválido.")
            
            if errores_validacion:
                for error in errores_validacion:
                    flash(error, "danger")
            else:
                if not cat_p_obj_para_sku or not cat_p_obj_para_sku.prefijo_sku:
                    flash(f"La categoría '{nombre_cat_principal_seleccionada}' no tiene un prefijo SKU configurado.", "danger")
                else:
                    nuevo_sku = generar_siguiente_sku(db, cat_p_obj_para_sku)
                    if not nuevo_sku: 
                        flash("No se pudo generar SKU. Verifica la configuración de contadores.", "danger")
                    else:
                        producto_existente_sku = db.query(Producto).filter(Producto.sku == nuevo_sku).first()
                        if producto_existente_sku:
                            flash(f"El SKU generado '{nuevo_sku}' ya existe.", "danger")
                        else:
                            datos_producto = {
                                "nombre_producto": nombre_producto, "sku": nuevo_sku,
                                "id_categoria_principal_producto": id_cat_principal_real,
                                "id_subcategoria_especifica_producto": id_s2_obj.id_subcategoria if id_s2_obj else None,
                                "descripcion_adicional": request.form.get('descripcion_adicional'),
                                "presentacion_compra": request.form.get('presentacion_compra'),
                                "cantidad_en_presentacion_compra": Decimal(request.form.get('cantidad_en_presentacion_compra')) if request.form.get('cantidad_en_presentacion_compra') else None,
                                "unidad_medida_base": request.form.get('unidad_medida_base'),
                                "es_indivisible": 'es_indivisible' in request.form,
                                "marca": request.form.get('marca'),
                                "sabor": request.form.get('sabor'), "color": request.form.get('color'),
                                "tamano_pulgadas": request.form.get('tamano_pulgadas'), "material": request.form.get('material'),
                                "dimensiones_capacidad": request.form.get('dimensiones_capacidad'), "tema_estilo": request.form.get('tema_estilo'),
                                "modalidad_servicio_directo": request.form.get('modalidad_servicio_directo'), 
                                "forma_tipo": request.form.get('forma_tipo'),
                                "dias_anticipacion_compra_proveedor": int(request.form.get('dias_anticipacion_compra_proveedor')) if request.form.get('dias_anticipacion_compra_proveedor') else None,
                                "modelo_sku_proveedor": request.form.get('modelo_sku_proveedor'),
                                "activo": True 
                            }
                            datos_producto_limpios = {k: v for k, v in datos_producto.items() if v is not None and (isinstance(v, bool) or str(v).strip() != '')}
                            
                            datos_producto_limpios['nombre_categoria_principal'] = nombre_cat_principal_seleccionada
                            datos_producto_limpios['nombre_subcategoria_nivel1'] = request.form.get('nombre_subcategoria_nivel1_seleccionada')
                            datos_producto_limpios['nombre_subcategoria_especifica'] = request.form.get('nombre_subcategoria_nivel2_seleccionada')
                            
                            datos_producto_limpios["descripcion_completa_generada"] = construir_descripcion_completa(datos_producto_limpios)
                            
                            nuevo_producto_obj = Producto(**datos_producto_limpios)
                            db.add(nuevo_producto_obj)
                            db.commit()
                            flash(f"Producto Interno '{nuevo_producto_obj.nombre_producto}' (SKU: {nuevo_producto_obj.sku}) creado.", "success")
                            return redirect(url_for('productos_bp.vista_listar_productos'))
            # Si hubo errores de validación o de SKU, se re-renderiza
            return render_template('crear_producto_unico.html',
                                   titulo_pagina="Crear Nuevo Producto Interno",
                                   categorias_jerarquia=categorias_jerarquia_data,
                                   request_form_data=request_form_data_repopulate)
        
        # Para el método GET
        return render_template('crear_producto_unico.html',
                               titulo_pagina="Crear Nuevo Producto Interno",
                               categorias_jerarquia=categorias_jerarquia_data,
                               request_form_data=request_form_data_repopulate)
    except ValueError as ve:
        if db.is_active: db.rollback()
        flash(f"Error de valor procesando el formulario: {ve}", "danger")
    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error general al crear el producto: {e}", "danger")
        import traceback
        traceback.print_exc()
    finally:
        if db.is_active: db.close()
    
    # Fallback render si hay una excepción no manejada antes del return del GET/POST
    # o si el POST tuvo errores y no se hizo redirect.
    # Asegurarse de que categorias_jerarquia_data esté definida incluso aquí.
    # Si la construcción inicial de categorias_jerarquia_data falló, podría estar vacía.
    # Una mejor práctica sería manejar la construcción de categorias_jerarquia_data
    # en un bloque try/except separado si es propensa a fallar,
    # pero para este error UndefinedError, asegurar que se pase es el objetivo principal.
    if not categorias_jerarquia_data: # Si la construcción inicial falló por alguna razón
        db_temp_fallback = SessionLocal()
        try:
            categorias_jerarquia_data = _build_categorias_jerarquia(db_temp_fallback)
        except Exception as e_fb_query:
            print(f"Error al construir categorias_jerarquia_data en fallback: {e_fb_query}")
            categorias_jerarquia_data = {} 
        finally:
            db_temp_fallback.close()

    return render_template('crear_producto_unico.html',
                           titulo_pagina="Crear Nuevo Producto Interno (Revisar Errores)",
                           categorias_jerarquia=categorias_jerarquia_data,
                           request_form_data=request_form_data_repopulate)


@productos_bp.route('/cargar', methods=['GET', 'POST'])
def vista_cargar_productos():
    # ... (sin cambios)
    if request.method == 'POST':
        if 'archivo_csv' not in request.files:
            flash('No se encontró la parte del archivo en la petición.', 'danger')
            return redirect(request.url) 
        file = request.files['archivo_csv']
        if file.filename == '':
            flash('Ningún archivo seleccionado.', 'warning')
            return redirect(url_for('productos_bp.vista_cargar_productos'))
        
        if file and file.filename.rsplit('.', 1)[1].lower() == 'csv':
            db_session_for_parse = SessionLocal()
            resultado_parseo = parsear_y_validar_csv_productos(db_session_for_parse, file.stream)
            db_session_for_parse.close() 

            session['productos_para_confirmar'] = resultado_parseo.get("productos_listos", [])
            session['errores_parseo'] = resultado_parseo.get("errores", [])
            if not resultado_parseo.get("productos_listos") and not resultado_parseo.get("errores"):
                flash("El archivo CSV parece estar vacío o no se pudo parsear correctamente con la nueva estructura.", "warning")
                return redirect(url_for('productos_bp.vista_cargar_productos'))
            return redirect(url_for('productos_bp.vista_confirmar_carga_productos'))
        else:
            flash('Tipo de archivo no permitido. Solo se permiten archivos .csv.', 'danger')
            return redirect(url_for('productos_bp.vista_cargar_productos'))

    session.pop('productos_para_confirmar', None)
    session.pop('errores_parseo', None)
    return render_template('cargar_productos.html', titulo_pagina="Cargar Productos Internos desde CSV")

@productos_bp.route('/confirmar-carga', methods=['GET', 'POST'])
def vista_confirmar_carga_productos():
    # ... (sin cambios)
    productos_para_confirmar = session.get('productos_para_confirmar', [])
    errores_parseo = session.get('errores_parseo', [])
    if not productos_para_confirmar and not errores_parseo:
        flash("No hay datos para confirmar. Por favor, sube un archivo CSV primero.", "warning")
        return redirect(url_for('productos_bp.vista_cargar_productos'))

    if request.method == 'POST':
        db_session = SessionLocal()
        try:
            if 'confirmar' in request.form:
                if productos_para_confirmar:
                    resultado_guardado = guardar_productos_en_bd(db_session, productos_para_confirmar)
                    flash(resultado_guardado.get("mensaje", "Proceso de guardado finalizado."), 'info')
                    if resultado_guardado.get("errores_detalle_guardado"):
                        for error in resultado_guardado.get("errores_detalle_guardado", []):
                            flash(error, 'danger')
                else:
                    flash("No había productos válidos para guardar después del parseo.", "warning")
            elif 'cancelar' in request.form:
                flash("Carga de productos cancelada por el usuario.", "info")
        except Exception as e:
            if db_session.is_active: db_session.rollback()
            flash(f'Ocurrió un error crítico durante el guardado: {str(e)}', 'danger')
        finally:
            if db_session.is_active: db_session.close()
        session.pop('productos_para_confirmar', None)
        session.pop('errores_parseo', None)
        return redirect(url_for('productos_bp.vista_listar_productos'))

    return render_template('confirmar_carga.html',
                           titulo_pagina="Confirmar Carga de Productos Internos",
                           productos=productos_para_confirmar,
                           errores=errores_parseo)
