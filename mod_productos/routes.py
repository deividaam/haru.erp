# /mod_productos/routes.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy.orm import Session, joinedload, selectinload, aliased, contains_eager
from sqlalchemy import asc, desc, or_, and_, func as sqlfunc, inspect
from decimal import Decimal

from . import productos_bp # Importar el blueprint
from database import SessionLocal # Asumiendo que database.py está en el directorio raíz
from models import Producto, Categoria, Subcategoria # Asumiendo que models.py está en el raíz
from utils_carga import ( # Asumiendo que utils_carga.py está en el raíz
    parsear_y_validar_csv_productos, guardar_productos_en_bd, construir_descripcion_completa,
    generar_siguiente_sku
)

# Funciones auxiliares que estaban en app.py y son específicas de productos
# (Si son muy genéricas, podrían ir a un archivo utils_productos.py, pero por ahora las dejamos aquí)
# Asegúrate de que estas funciones ahora usen 'productos_bp.route' si fueran rutas,
# o que sean llamadas correctamente por las rutas del blueprint.

# Estas funciones auxiliares NO son rutas, así que no necesitan el decorador del blueprint.
# Simplemente se usan internamente por las rutas de este blueprint.
def get_producto_by_id_for_edit(db: Session, id_producto: int) -> Producto | None:
    CatPrincAlias = aliased(Categoria, name="cat_princ_edit_alias")
    SubcatEspAlias = aliased(Subcategoria, name="sub_esp_edit_alias")
    CatDeSubcatAlias = aliased(Categoria, name="cat_de_sub_edit_alias")

    return db.query(Producto)\
        .outerjoin(CatPrincAlias, Producto.id_categoria_principal_producto == CatPrincAlias.id_categoria)\
        .outerjoin(SubcatEspAlias, Producto.id_subcategoria_especifica_producto == SubcatEspAlias.id_subcategoria)\
        .outerjoin(CatDeSubcatAlias, SubcatEspAlias.id_categoria_contenedora == CatDeSubcatAlias.id_categoria)\
        .options(
            contains_eager(Producto.categoria_principal_producto, alias=CatPrincAlias),
            contains_eager(Producto.subcategoria_especifica_producto, alias=SubcatEspAlias)
                .contains_eager(Subcategoria.categoria_contenedora, alias=CatDeSubcatAlias)
        )\
        .filter(Producto.id_producto == id_producto).first()

def update_producto_db(db: Session, id_producto: int, datos_actualizacion: dict) -> Producto | None:
    producto_db = get_producto_by_id_for_edit(db, id_producto)
    if not producto_db:
        return None
    campos_actualizables = [
        "nombre_producto", "id_categoria_principal_producto", "id_subcategoria_especifica_producto",
        "descripcion_adicional", "presentacion_compra", "cantidad_en_presentacion_compra",
        "unidad_medida_base", "sabor", "color", "tamano_pulgadas", "material",
        "dimensiones_capacidad", "tema_estilo", "modalidad_servicio_directo", "forma_tipo",
        "dias_anticipacion_compra_proveedor", "activo"
    ]
    cambios_hechos = False
    for campo in campos_actualizables:
        if campo in datos_actualizacion:
            valor_actualizar = datos_actualizacion[campo]
            if campo == "activo":
                valor_actualizar = True if valor_actualizar == 'on' or valor_actualizar is True else False
            elif campo in ["id_categoria_principal_producto", "id_subcategoria_especifica_producto", "dias_anticipacion_compra_proveedor"]:
                if valor_actualizar == '' or valor_actualizar is None:
                    valor_actualizar = None
                else:
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
            if getattr(producto_db, campo) != valor_actualizar:
                setattr(producto_db, campo, valor_actualizar)
                cambios_hechos = True
    if cambios_hechos:
        datos_para_desc = {c.key: getattr(producto_db, c.key) for c in inspect(producto_db).mapper.column_attrs}
        producto_db.descripcion_completa_generada = construir_descripcion_completa(datos_para_desc)
    try:
        db.commit()
        db.refresh(producto_db)
        return producto_db
    except Exception as e:
        db.rollback()
        print(f"Error al actualizar producto ID {id_producto}: {e}")
        raise e

def _construir_query_productos_filtrados(db_session: Session, args: dict):
    # ... (Misma lógica que tenías en app.py, asegúrate que las referencias a modelos sean correctas)
    search_query = args.get('q', '').strip()
    categoria_principal_id_filter = args.get('id_categoria_principal_producto', type=int)
    subcategoria_especifica_id_filter = args.get('id_subcategoria_especifica_producto', type=int)
    sabor_filter = args.get('sabor', '').strip()
    color_filter = args.get('color', '').strip()
    material_filter = args.get('material', '').strip()
    sort_by_param = args.get('sort_by', 'nombre')
    sort_order_param = args.get('sort_order', 'asc')

    CatPrincAlias = aliased(Categoria, name="cat_princ_alias_bp") # Cambiado el alias para evitar colisiones si se usa en otro lado
    SubcatEspAlias = aliased(Subcategoria, name="sub_esp_alias_bp")
    CatDeSubcatAlias = aliased(Categoria, name="cat_de_sub_alias_filter_bp")

    query = db_session.query(Producto)\
        .outerjoin(CatPrincAlias, Producto.id_categoria_principal_producto == CatPrincAlias.id_categoria)\
        .outerjoin(SubcatEspAlias, Producto.id_subcategoria_especifica_producto == SubcatEspAlias.id_subcategoria)\
        .outerjoin(CatDeSubcatAlias, SubcatEspAlias.id_categoria_contenedora == CatDeSubcatAlias.id_categoria)

    query = query.options(
        contains_eager(Producto.categoria_principal_producto, alias=CatPrincAlias),
        contains_eager(Producto.subcategoria_especifica_producto, alias=SubcatEspAlias)
            .contains_eager(Subcategoria.categoria_contenedora, alias=CatDeSubcatAlias)
    )
    sortable_columns = {
        "id": Producto.id_producto, "sku": Producto.sku, "nombre": Producto.nombre_producto,
        "categoria_principal": sqlfunc.coalesce(CatPrincAlias.nombre_categoria, CatDeSubcatAlias.nombre_categoria),
        "subcategoria_especifica": SubcatEspAlias.nombre_subcategoria,
        "presentacion_compra": Producto.presentacion_compra, "activo": Producto.activo
    }
    column_to_sort_expression = sortable_columns.get(sort_by_param, Producto.nombre_producto)
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(or_(Producto.nombre_producto.ilike(search_term), Producto.sku.ilike(search_term), Producto.descripcion_completa_generada.ilike(search_term)))
    if categoria_principal_id_filter:
        query = query.filter(or_(Producto.id_categoria_principal_producto == categoria_principal_id_filter, SubcatEspAlias.id_categoria_contenedora == categoria_principal_id_filter))
    if subcategoria_especifica_id_filter:
        query = query.filter(Producto.id_subcategoria_especifica_producto == subcategoria_especifica_id_filter)
    if sabor_filter: query = query.filter(Producto.sabor.ilike(f"%{sabor_filter}%"))
    if color_filter: query = query.filter(Producto.color.ilike(f"%{color_filter}%"))
    if material_filter: query = query.filter(Producto.material.ilike(f"%{material_filter}%"))
    order_final_expression = desc(column_to_sort_expression) if sort_order_param == 'desc' else asc(column_to_sort_expression)
    query = query.order_by(order_final_expression, Producto.id_producto)
    return query, sort_by_param, sort_order_param

def obtener_info_precios_producto(db: Session, id_producto: int) -> dict:
    # ... (Misma lógica que tenías en app.py, asegúrate que las referencias a modelos sean correctas)
    # Nota: Esta función usa DetalleCompra, EncabezadoCompra, Proveedor. Asegúrate que estén importados.
    from models import DetalleCompra, EncabezadoCompra, Proveedor # Añadir si no están ya
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


# Rutas del Blueprint de Productos
# El prefijo '/productos' ya está definido en el Blueprint en __init__.py
# Así que aquí las rutas son relativas a ese prefijo.

PORCENTAJE_AUMENTO_MENSUAL_EST = 0.005 # Definir la constante si se usa aquí

@productos_bp.route('/', methods=['GET']) # Antes era /productos
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
        subcategorias_db = db_session.query(Subcategoria).order_by(Subcategoria.nombre_subcategoria).all()
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
        sortable_columns_keys = ["id", "sku", "nombre", "categoria_principal", "subcategoria_especifica", "presentacion_compra", "activo"]

        return render_template('listar_productos.html',
                               productos=productos_enriquecidos,
                               titulo_pagina="Listado de Productos Internos",
                               current_sort=current_sort,
                               sortable_column_keys=sortable_columns_keys,
                               categorias=categorias_db, subcategorias=subcategorias_db,
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

@productos_bp.route('/api/filtrar', methods=['GET']) # Antes /productos/api/filtrar
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
        sortable_columns_keys = ["id", "sku", "nombre", "categoria_principal", "subcategoria_especifica", "presentacion_compra", "activo"]
        return render_template('_tabla_productos_parcial.html',
                               productos=productos_enriquecidos_api,
                               current_sort=current_sort, sortable_column_keys=sortable_columns_keys,
                               request_args=request.args, aumento_mensual_est=PORCENTAJE_AUMENTO_MENSUAL_EST)
    except Exception as e:
        print(f"Error en API filtrar productos: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()

@productos_bp.route('/api/buscar_por_descripcion', methods=['GET']) # Antes /productos/api/buscar_por_descripcion
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

@productos_bp.route('/<int:id_producto>/editar', methods=['GET', 'POST']) # Antes /productos/<int:id_producto>/editar
def vista_editar_producto(id_producto):
    db = SessionLocal()
    producto_a_editar = get_producto_by_id_for_edit(db, id_producto)
    form_data_repopulate = {}
    if not producto_a_editar:
        flash(f"Producto Interno con ID {id_producto} no encontrado.", "danger")
        db.close()
        return redirect(url_for('productos_bp.vista_listar_productos')) # Actualizar url_for

    if request.method == 'POST':
        form_data_repopulate = request.form.to_dict()
        try:
            datos_formulario = {
                "nombre_producto": request.form.get('nombre_producto'),
                "id_categoria_principal_producto": request.form.get('id_categoria_principal_producto'),
                "id_subcategoria_especifica_producto": request.form.get('id_subcategoria_especifica_producto'),
                "descripcion_adicional": request.form.get('descripcion_adicional'),
                "presentacion_compra": request.form.get('presentacion_compra'),
                "cantidad_en_presentacion_compra": request.form.get('cantidad_en_presentacion_compra'),
                "unidad_medida_base": request.form.get('unidad_medida_base'),
                "sabor": request.form.get('sabor'), "color": request.form.get('color'),
                "tamano_pulgadas": request.form.get('tamano_pulgadas'), "material": request.form.get('material'),
                "dimensiones_capacidad": request.form.get('dimensiones_capacidad'), "tema_estilo": request.form.get('tema_estilo'),
                "modalidad_servicio_directo": request.form.get('modalidad_servicio_directo'), "forma_tipo": request.form.get('forma_tipo'),
                "dias_anticipacion_compra_proveedor": request.form.get('dias_anticipacion_compra_proveedor'),
                "activo": request.form.get('activo')
            }
            datos_actualizacion = {k: v for k, v in datos_formulario.items() if v is not None and (isinstance(v, bool) or str(v).strip() != '')}
            if 'activo' not in datos_actualizacion: datos_actualizacion['activo'] = False
            elif datos_actualizacion['activo'] == 'on': datos_actualizacion['activo'] = True
            update_producto_db(db, id_producto, datos_actualizacion)
            flash(f"Producto Interno '{producto_a_editar.nombre_producto}' actualizado exitosamente.", "success")
            return redirect(url_for('productos_bp.vista_listar_productos')) # Actualizar url_for
        except ValueError as ve:
             if db.is_active: db.rollback()
             flash(f"Error en los datos del formulario al editar: {str(ve)}", "danger")
        except Exception as e:
            if db.is_active: db.rollback()
            flash(f"Error al actualizar el producto interno: {str(e)}", "danger")

    categorias_db_form = db.query(Categoria).filter(Categoria.id_categoria_padre == None).order_by(Categoria.nombre_categoria).all()
    subcategorias_db_form = db.query(Subcategoria).order_by(Subcategoria.nombre_subcategoria).all()
    db.close()
    return render_template('editar_producto.html',
                           titulo_pagina=f"Editar Producto Interno: {producto_a_editar.nombre_producto}",
                           producto=producto_a_editar, request_form_data_repopulate=form_data_repopulate,
                           categorias_para_select=categorias_db_form, subcategorias_para_select=subcategorias_db_form)

@productos_bp.route('/crear', methods=['GET', 'POST']) # Antes /productos/crear
def vista_crear_producto_unico():
    db = SessionLocal()
    try:
        categorias_para_select = db.query(Categoria).filter(Categoria.id_categoria_padre == None).order_by(Categoria.nombre_categoria).all()
        subcategorias_para_select = db.query(Subcategoria).order_by(Subcategoria.nombre_subcategoria).all()
        request_form_data_repopulate = {}
        if request.method == 'POST':
            request_form_data_repopulate = request.form.to_dict()
            # ... (lógica de creación de producto que tenías, asegurando que url_for se actualice si es necesario) ...
            nombre_producto = request.form.get('nombre_producto', '').strip()
            # (resto de la lógica de validación y creación)
            # ...
            # Ejemplo de redirección al final:
            # return redirect(url_for('productos_bp.vista_listar_productos'))
            # ... (código de creación de producto copiado y adaptado de app.py)
            nombre_producto = request.form.get('nombre_producto', '').strip()
            errores_validacion = []

            id_categoria_str = request.form.get('id_categoria_principal_producto')
            id_categoria_form = None
            if id_categoria_str and id_categoria_str.isdigit():
                id_categoria_form = int(id_categoria_str)
            elif id_categoria_str and id_categoria_str != "":
                errores_validacion.append("Valor inválido para ID de Categoría Principal.")

            id_subcategoria_str = request.form.get('id_subcategoria_especifica_producto')
            id_subcategoria_form = None
            if id_subcategoria_str and id_subcategoria_str.isdigit():
                id_subcategoria_form = int(id_subcategoria_str)
            elif id_subcategoria_str and id_subcategoria_str != "":
                 errores_validacion.append("Valor inválido para ID de Subcategoría Específica.")

            if not nombre_producto:
                errores_validacion.append("Nombre del producto es obligatorio.")
            if not id_categoria_form and not id_subcategoria_form:
                errores_validacion.append("Debe seleccionar una Categoría Principal o una Subcategoría Específica.")
            
            categoria_obj = None
            if id_categoria_form:
                categoria_obj = db.query(Categoria).get(id_categoria_form)
                if not categoria_obj:
                    errores_validacion.append("Categoría principal seleccionada no es válida.")
            
            subcategoria_obj = None
            if id_subcategoria_form:
                subcategoria_obj = db.query(Subcategoria).get(id_subcategoria_form)
                if not subcategoria_obj:
                     errores_validacion.append("Subcategoría específica seleccionada no es válida.")
            
            if errores_validacion:
                for error in errores_validacion:
                    flash(error, "danger")
                # No cerrar db aquí, se cierra en finally
                return render_template('crear_producto_unico.html',
                                       titulo_pagina="Crear Nuevo Producto Interno",
                                       categorias_para_select=categorias_para_select,
                                       subcategorias_para_select=subcategorias_para_select,
                                       request_form_data=request_form_data_repopulate)

            categoria_para_sku = None
            if categoria_obj and categoria_obj.prefijo_sku:
                categoria_para_sku = categoria_obj
            elif subcategoria_obj:
                current_cat_ancestor = subcategoria_obj.categoria_contenedora
                while current_cat_ancestor:
                    if current_cat_ancestor.prefijo_sku:
                        categoria_para_sku = current_cat_ancestor
                        break
                    if hasattr(current_cat_ancestor, 'categoria_padre'):
                        current_cat_ancestor = current_cat_ancestor.categoria_padre
                    else: 
                        current_cat_ancestor = None
            if not categoria_para_sku or not categoria_para_sku.prefijo_sku:
                flash("No se pudo determinar una categoría con prefijo SKU.", "danger")
                return render_template('crear_producto_unico.html', titulo_pagina="Crear Nuevo Producto Interno", categorias_para_select=categorias_para_select, subcategorias_para_select=subcategorias_para_select, request_form_data=request_form_data_repopulate)

            nuevo_sku = generar_siguiente_sku(db, categoria_para_sku)
            if not nuevo_sku: 
                flash("No se pudo generar SKU. Verifica la configuración de contadores para la categoría relevante.", "danger")
                return render_template('crear_producto_unico.html', titulo_pagina="Crear Nuevo Producto Interno", categorias_para_select=categorias_para_select, subcategorias_para_select=subcategorias_para_select, request_form_data=request_form_data_repopulate)

            producto_existente_sku = db.query(Producto).filter(Producto.sku == nuevo_sku).first()
            if producto_existente_sku:
                flash(f"El SKU generado '{nuevo_sku}' ya existe. Intenta de nuevo o revisa los contadores.", "danger")
                return render_template('crear_producto_unico.html', titulo_pagina="Crear Nuevo Producto Interno", categorias_para_select=categorias_para_select, subcategorias_para_select=subcategorias_para_select, request_form_data=request_form_data_repopulate)

            datos_producto = {
                "nombre_producto": nombre_producto, "sku": nuevo_sku,
                "id_categoria_principal_producto": id_categoria_form,
                "id_subcategoria_especifica_producto": id_subcategoria_form,
                "descripcion_adicional": request.form.get('descripcion_adicional'),
                "presentacion_compra": request.form.get('presentacion_compra'),
                "cantidad_en_presentacion_compra": Decimal(request.form.get('cantidad_en_presentacion_compra')) if request.form.get('cantidad_en_presentacion_compra') else None,
                "unidad_medida_base": request.form.get('unidad_medida_base'),
                "sabor": request.form.get('sabor'), "color": request.form.get('color'),
                "tamano_pulgadas": request.form.get('tamano_pulgadas'), "material": request.form.get('material'),
                "dimensiones_capacidad": request.form.get('dimensiones_capacidad'), "tema_estilo": request.form.get('tema_estilo'),
                "modalidad_servicio_directo": request.form.get('modalidad_servicio_directo'), "forma_tipo": request.form.get('forma_tipo'),
                "dias_anticipacion_compra_proveedor": int(request.form.get('dias_anticipacion_compra_proveedor')) if request.form.get('dias_anticipacion_compra_proveedor') else None,
                "activo": True
            }
            datos_producto_limpios = {k: v for k, v in datos_producto.items() if v is not None and str(v).strip() != ''}
            if datos_producto_limpios.get("nombre_producto"):
                 datos_producto_limpios["descripcion_completa_generada"] = construir_descripcion_completa(datos_producto_limpios)
            else:
                 datos_producto_limpios["descripcion_completa_generada"] = "Descripción no disponible"

            nuevo_producto_obj = Producto(**datos_producto_limpios)
            db.add(nuevo_producto_obj)
            db.commit()
            flash(f"Producto Interno '{nuevo_producto_obj.nombre_producto}' (SKU: {nuevo_producto_obj.sku}) creado.", "success")
            return redirect(url_for('productos_bp.vista_listar_productos'))


        return render_template('crear_producto_unico.html',
                               titulo_pagina="Crear Nuevo Producto Interno",
                               categorias_para_select=categorias_para_select,
                               subcategorias_para_select=subcategorias_para_select,
                               request_form_data=request_form_data_repopulate)
    except ValueError as ve:
        if db.is_active: db.rollback()
        flash(f"Error de valor procesando el formulario: {ve}", "danger")
    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error general al crear el producto: {e}", "danger")
    finally:
        if db.is_active: db.close()
    # Este return es por si hay una excepción antes del return del GET o POST
    # y la sesión de db ya se cerró en el finally.
    # Es mejor obtener los datos para el template fuera del try/except/finally principal si es posible,
    # o reabrir una sesión si es necesario para el renderizado de error.
    db_temp_for_render = SessionLocal()
    cats_render = db_temp_for_render.query(Categoria).filter(Categoria.id_categoria_padre == None).order_by(Categoria.nombre_categoria).all()
    subcats_render = db_temp_for_render.query(Subcategoria).order_by(Subcategoria.nombre_subcategoria).all()
    db_temp_for_render.close()
    return render_template('crear_producto_unico.html',
                           titulo_pagina="Crear Nuevo Producto Interno",
                           categorias_para_select=cats_render,
                           subcategorias_para_select=subcats_render,
                           request_form_data=request.form.to_dict() if request.method == 'POST' else {})


@productos_bp.route('/cargar', methods=['GET', 'POST']) # Antes /productos/cargar
def vista_cargar_productos():
    if request.method == 'POST':
        # ... (lógica de carga de CSV que tenías, asegurando que url_for se actualice)
        if 'archivo_csv' not in request.files:
            flash('No se encontró la parte del archivo en la petición.', 'danger')
            return redirect(request.url) # request.url podría necesitar ser url_for('productos_bp.vista_cargar_productos')
        file = request.files['archivo_csv']
        if file.filename == '':
            flash('Ningún archivo seleccionado.', 'warning')
            return redirect(url_for('productos_bp.vista_cargar_productos'))
        if file and utils_carga.allowed_file(file.filename): # Asumiendo que allowed_file está en utils_carga
            resultado_parseo = parsear_y_validar_csv_productos(file.stream)
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

@productos_bp.route('/confirmar-carga', methods=['GET', 'POST']) # Antes /productos/confirmar-carga
def vista_confirmar_carga_productos():
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
