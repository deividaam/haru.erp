# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from sqlalchemy.orm import Session, joinedload, aliased, contains_eager, subqueryload
from sqlalchemy import asc, desc, or_, and_, func as sqlfunc, exc as sqlalchemy_exc, cast, DECIMAL as SQLDECIMAL
from database import SessionLocal, create_tables
from utils_carga import (
    parsear_y_validar_csv_productos, guardar_productos_en_bd, construir_descripcion_completa,
    parsear_y_validar_csv_precios, guardar_precios_en_bd,
    get_or_create_categoria, get_or_create_subcategoria, generar_siguiente_sku,
    MAPEO_CATEGORIA_PREFIJO_SKU # Importar el mapeo para los prefijos
)
from datetime import date, datetime

from models import (
    Producto, Categoria, Subcategoria, Proveedor,
    PrecioProveedor, EncabezadoCompra, DetalleCompra
)

app = Flask(__name__)
app.secret_key = os.urandom(24)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

PORCENTAJE_AUMENTO_MENSUAL_EST = 0.005

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

try:
    if __name__ == '__main__':
        print("Intentando crear tablas si no existen (desde app.py)...")
        create_tables()
except Exception as e:
    print(f"Error al intentar crear tablas desde app.py: {e}")


# Definición de campos obligatorios por categoría para el formulario
# Las claves deben coincidir con los nombres de categoría definidos en TODAS_LAS_CATEGORIAS_NOMBRES
# Los valores de 'fields' deben coincidir con los atributos 'name' de los inputs en el HTML
CAMPOS_OBLIGATORIOS_FORM_POR_CATEGORIA = {
    "Dulces/Golosinas": {
        "fields": ["nombre_subcategoria", "presentacion", "cantidad_por_presentacion", "unidad_medida_venta", "sabor", "dias_anticipacion_compra"],
        "labels": ["Subcategoría", "Presentación", "Cantidad por Presentación", "Unidad de Medida Venta", "Sabor", "Días Anticipación Compra"]
    },
    "Globos": {
        "fields": ["nombre_subcategoria", "presentacion", "cantidad_por_presentacion", "unidad_medida_venta", "color", "tamano_pulgadas", "dias_anticipacion_compra"],
        "labels": ["Subcategoría", "Presentación", "Cantidad por Presentación", "Unidad de Medida Venta", "Color", "Tamaño (Pulgadas)", "Días Anticipación Compra"]
    },
    "Decoración": {
        "fields": ["nombre_subcategoria", "presentacion", "cantidad_por_presentacion", "color", "dias_anticipacion_compra"],
        "labels": ["Subcategoría", "Presentación", "Cantidad por Presentación", "Color", "Días Anticipación Compra"]
    },
    "Display": { # Nombre estandarizado
        "fields": ["nombre_subcategoria", "presentacion", "cantidad_por_presentacion", "color", "material", "dias_anticipacion_compra"],
        "labels": ["Subcategoría", "Presentación", "Cantidad por Presentación", "Color", "Material", "Días Anticipación Compra"]
    },
    "Servicios": {
        "fields": ["nombre_subcategoria", "modalidad_servicio", "descripcion_adicional", "dias_anticipacion_compra"],
        "labels": ["Subcategoría", "Modalidad de Servicio", "Descripción Adicional", "Días Anticipación Compra"]
    }
}

# Lista maestra de nombres de categorías para el formulario
TODAS_LAS_CATEGORIAS_NOMBRES = ["Dulces/Golosinas", "Globos", "Decoración", "Display", "Servicios"]


def get_producto_by_id_for_edit(db: Session, id_producto: int) -> Producto | None:
    # ... (código existente sin cambios)
    CategoriaDirectaAlias = aliased(Categoria, name="cat_directa_edit_alias")
    SubcategoriaAlias = aliased(Subcategoria, name="sub_cat_edit_alias")
    CategoriaDeSubAlias = aliased(Categoria, name="cat_de_sub_edit_alias")
    return db.query(Producto)\
        .outerjoin(CategoriaDirectaAlias, Producto.id_categoria_directa == CategoriaDirectaAlias.id_categoria)\
        .outerjoin(SubcategoriaAlias, Producto.id_subcategoria == SubcategoriaAlias.id_subcategoria)\
        .outerjoin(CategoriaDeSubAlias, SubcategoriaAlias.id_categoria == CategoriaDeSubAlias.id_categoria)\
        .options(
            contains_eager(Producto.categoria_directa, alias=CategoriaDirectaAlias),
            contains_eager(Producto.subcategoria, alias=SubcategoriaAlias)
                .contains_eager(Subcategoria.categoria, alias=CategoriaDeSubAlias)
        )\
        .filter(Producto.id_producto == id_producto).first()

def update_producto_db(db: Session, id_producto: int, datos_actualizacion: dict) -> Producto | None:
    # ... (código existente sin cambios)
    producto_db = get_producto_by_id_for_edit(db, id_producto)
    if not producto_db: return None
    campos_actualizables = [
        "nombre_producto", "descripcion_adicional", "presentacion",
        "cantidad_por_presentacion", "unidad_medida_venta", "sabor", "color",
        "tamano_pulgadas", "material", "dimensiones_capacidad", "tema_estilo",
        "modalidad_servicio", "activo", "forma_tipo", "dias_anticipacion_compra"
    ]
    cambios_hechos = False
    for campo in campos_actualizables:
        if campo in datos_actualizacion:
            valor_actualizar = datos_actualizacion[campo]
            if campo == "activo":
                valor_actualizar = True if valor_actualizar == 'on' or valor_actualizar is True else False
            if getattr(producto_db, campo) != valor_actualizar:
                setattr(producto_db, campo, valor_actualizar)
                cambios_hechos = True
    if cambios_hechos:
        datos_para_desc = {c.name: getattr(producto_db, c.name) for c in producto_db.__table__.columns if hasattr(producto_db, c.name)}
        for key, value in datos_actualizacion.items():
            if key in datos_para_desc:
                datos_para_desc[key] = value
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
    # ... (código existente sin cambios)
    search_query = args.get('q', '').strip()
    categoria_id_filter = args.get('categoria_id', type=int)
    subcategoria_id_filter = args.get('subcategoria_id', type=int)
    sabor_filter = args.get('sabor', '').strip()
    color_filter = args.get('color', '').strip()
    material_filter = args.get('material', '').strip()
    sort_by_param = args.get('sort_by', 'nombre')
    sort_order_param = args.get('sort_order', 'asc')
    CategoriaDirectaAlias = aliased(Categoria, name="cat_directa_alias")
    SubcategoriaAlias = aliased(Subcategoria, name="sub_alias")
    CategoriaDeSubAlias = aliased(Categoria, name="cat_de_sub_alias")
    query = db_session.query(Producto)\
        .outerjoin(CategoriaDirectaAlias, Producto.id_categoria_directa == CategoriaDirectaAlias.id_categoria)\
        .outerjoin(SubcategoriaAlias, Producto.id_subcategoria == SubcategoriaAlias.id_subcategoria)\
        .outerjoin(CategoriaDeSubAlias, SubcategoriaAlias.id_categoria == CategoriaDeSubAlias.id_categoria)
    query = query.options(
        contains_eager(Producto.categoria_directa, alias=CategoriaDirectaAlias),
        contains_eager(Producto.subcategoria, alias=SubcategoriaAlias)
            .contains_eager(Subcategoria.categoria, alias=CategoriaDeSubAlias)
    )
    sortable_columns = {
        "id": Producto.id_producto, "sku": Producto.sku, "nombre": Producto.nombre_producto,
        "categoria": sqlfunc.coalesce(CategoriaDirectaAlias.nombre_categoria, CategoriaDeSubAlias.nombre_categoria),
        "subcategoria": SubcategoriaAlias.nombre_subcategoria,
        "presentacion": Producto.presentacion, "activo": Producto.activo
    }
    column_to_sort_expression = sortable_columns.get(sort_by_param, Producto.nombre_producto)
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            or_(
                Producto.nombre_producto.ilike(search_term),
                Producto.sku.ilike(search_term),
                Producto.descripcion_completa_generada.ilike(search_term)
            )
        )
    if categoria_id_filter:
        query = query.filter(
            or_(
                CategoriaDirectaAlias.id_categoria == categoria_id_filter,
                CategoriaDeSubAlias.id_categoria == categoria_id_filter
            )
        )
    if subcategoria_id_filter:
        query = query.filter(SubcategoriaAlias.id_subcategoria == subcategoria_id_filter)
    if sabor_filter:
        query = query.filter(Producto.sabor.ilike(f"%{sabor_filter}%"))
    if color_filter:
        query = query.filter(Producto.color.ilike(f"%{color_filter}%"))
    if material_filter:
        query = query.filter(Producto.material.ilike(f"%{material_filter}%"))
    order_final_expression = desc(column_to_sort_expression) if sort_order_param == 'desc' else asc(column_to_sort_expression)
    query = query.order_by(order_final_expression)
    return query, sort_by_param, sort_order_param

def obtener_info_precios_producto(db: Session, id_producto: int) -> dict:
    # ... (código existente sin cambios)
    info = {
        "precio_min": None, "proveedor_min": None, "disponibilidad_min": None,
        "precio_max": None, "proveedor_max": None, "disponibilidad_max": None
    }
    subq_ultima_compra_por_proveedor = db.query(
        DetalleCompra.id_encabezado_compra,
        EncabezadoCompra.id_proveedor,
        DetalleCompra.disponibilidad_proveedor,
        sqlfunc.row_number().over(
            partition_by=EncabezadoCompra.id_proveedor,
            order_by=desc(EncabezadoCompra.fecha_documento)
        ).label('rn')
    ).join(EncabezadoCompra, DetalleCompra.id_encabezado_compra == EncabezadoCompra.id_encabezado_compra)\
    .filter(DetalleCompra.id_producto == id_producto)\
    .subquery()
    detalles_con_proveedor_y_disp = db.query(
        DetalleCompra.costo_unitario_compra,
        Proveedor.nombre_proveedor,
        subq_ultima_compra_por_proveedor.c.disponibilidad_proveedor.label("ultima_disponibilidad")
    ).select_from(DetalleCompra)\
    .join(EncabezadoCompra, DetalleCompra.id_encabezado_compra == EncabezadoCompra.id_encabezado_compra)\
    .join(Proveedor, EncabezadoCompra.id_proveedor == Proveedor.id_proveedor)\
    .outerjoin(
        subq_ultima_compra_por_proveedor,
        and_(
            EncabezadoCompra.id_proveedor == subq_ultima_compra_por_proveedor.c.id_proveedor,
            subq_ultima_compra_por_proveedor.c.rn == 1
        )
    )\
    .filter(DetalleCompra.id_producto == id_producto)\
    .all()
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

@app.route('/')
def index():
    # ... (código existente sin cambios)
    return redirect(url_for('vista_listar_productos'))

@app.route('/productos/cargar', methods=['GET', 'POST'])
def vista_cargar_productos():
    # ... (código existente sin cambios)
    if request.method == 'POST':
        if 'archivo_csv' not in request.files:
            flash('No se encontró la parte del archivo en la petición.', 'danger')
            return redirect(request.url)
        file = request.files['archivo_csv']
        if file.filename == '':
            flash('Ningún archivo seleccionado.', 'warning')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            resultado_parseo = parsear_y_validar_csv_productos(file.stream)
            session['productos_para_confirmar'] = resultado_parseo.get("productos_listos", [])
            session['errores_parseo'] = resultado_parseo.get("errores", [])
            if not resultado_parseo.get("productos_listos") and not resultado_parseo.get("errores"):
                flash("El archivo CSV parece estar vacío o no se pudo parsear correctamente.", "warning")
                return redirect(url_for('vista_cargar_productos'))
            return redirect(url_for('vista_confirmar_carga'))
        else:
            flash('Tipo de archivo no permitido. Solo se permiten archivos .csv.', 'danger')
            return redirect(request.url)
    session.pop('productos_para_confirmar', None)
    session.pop('errores_parseo', None)
    return render_template('cargar_productos.html', titulo_pagina="Cargar Productos desde CSV")

@app.route('/productos/confirmar_carga', methods=['GET', 'POST'])
def vista_confirmar_carga():
    # ... (código existente sin cambios)
    productos_para_confirmar = session.get('productos_para_confirmar', [])
    errores_parseo = session.get('errores_parseo', [])
    if not productos_para_confirmar and not errores_parseo:
        flash("No hay datos para confirmar. Por favor, sube un archivo CSV primero.", "warning")
        return redirect(url_for('vista_cargar_productos'))
    if request.method == 'POST':
        if 'confirmar' in request.form:
            db_session = SessionLocal()
            try:
                if productos_para_confirmar:
                    resultado_guardado = guardar_productos_en_bd(db_session, productos_para_confirmar)
                    flash(resultado_guardado.get("mensaje", "Proceso de guardado finalizado."), 'info')
                    if resultado_guardado.get("errores_detalle_guardado"):
                        for error in resultado_guardado.get("errores_detalle_guardado", []):
                            flash(error, 'danger')
                else:
                    flash("No había productos válidos para guardar después del parseo.", "warning")
            except Exception as e:
                db_session.rollback()
                flash(f'Ocurrió un error crítico durante el guardado: {str(e)}', 'danger')
            finally:
                db_session.close()
            session.pop('productos_para_confirmar', None)
            session.pop('errores_parseo', None)
            return redirect(url_for('vista_listar_productos'))
        elif 'cancelar' in request.form:
            flash("Carga de productos cancelada por el usuario.", "info")
            session.pop('productos_para_confirmar', None)
            session.pop('errores_parseo', None)
            return redirect(url_for('vista_cargar_productos'))
    return render_template('confirmar_carga.html',
                           titulo_pagina="Confirmar Carga de Productos",
                           productos=productos_para_confirmar,
                           errores=errores_parseo)

@app.route('/productos/crear', methods=['GET', 'POST'])
def vista_crear_producto_unico():
    db = SessionLocal()
    # Usar TODAS_LAS_CATEGORIAS_NOMBRES para el dropdown del formulario
    categorias_para_select = TODAS_LAS_CATEGORIAS_NOMBRES
    request_form_data_repopulate = request.form.to_dict() if request.method == 'POST' else {}

    try:
        if request.method == 'POST':
            nombre_producto = request.form.get('nombre_producto', '').strip()
            # El formulario ahora envía el nombre de la categoría, no el ID
            categoria_nombre_form = request.form.get('categoria_seleccionada', '').strip()
            nombre_subcategoria_form = request.form.get('nombre_subcategoria', '').strip() or None

            errores_validacion = []
            if not nombre_producto:
                errores_validacion.append("Nombre del producto es obligatorio.")
            if not categoria_nombre_form:
                errores_validacion.append("Categoría es obligatoria.")
            
            categoria_obj = None
            if categoria_nombre_form:
                # Obtener o crear la categoría usando su nombre
                # El prefijo SKU se tomará del mapeo si la categoría es nueva
                prefijo_sugerido = MAPEO_CATEGORIA_PREFIJO_SKU.get(categoria_nombre_form)
                categoria_obj = get_or_create_categoria(db, categoria_nombre_form, prefijo_sugerido)
                if not categoria_obj: # Esto no debería ocurrir si get_or_create_categoria funciona
                    errores_validacion.append("Error al procesar la categoría seleccionada.")
                else:
                    # Validación de campos obligatorios por categoría
                    definicion_obligatorios = CAMPOS_OBLIGATORIOS_FORM_POR_CATEGORIA.get(categoria_obj.nombre_categoria)
                    if definicion_obligatorios:
                        for i, campo_name in enumerate(definicion_obligatorios["fields"]):
                            valor_campo = request.form.get(campo_name, '').strip()
                            # Considerar que algunos campos obligatorios podrían ser selects
                            if not valor_campo and campo_name not in ['nombre_subcategoria', 'presentacion', 'unidad_medida_venta', 'material', 'modalidad_servicio']: # Excluir selects que tienen su propio manejo de placeholder
                                errores_validacion.append(f"El campo '{definicion_obligatorios['labels'][i]}' es obligatorio para la categoría '{categoria_obj.nombre_categoria}'.")
                            elif campo_name in ['nombre_subcategoria', 'presentacion', 'unidad_medida_venta', 'material', 'modalidad_servicio'] and not valor_campo:
                                 # Para selects, un valor vacío después del placeholder indica que no se seleccionó nada válido
                                errores_validacion.append(f"Debe seleccionar una opción para '{definicion_obligatorios['labels'][i]}' en la categoría '{categoria_obj.nombre_categoria}'.")


            if errores_validacion:
                for error in errores_validacion:
                    flash(error, "danger")
                return render_template('crear_producto_unico.html',
                                       titulo_pagina="Crear Nuevo Producto",
                                       categorias_para_select=categorias_para_select, # Pasar la lista de nombres
                                       request_form_data=request_form_data_repopulate)

            subcategoria_obj = None
            if nombre_subcategoria_form and categoria_obj:
                subcategoria_obj = get_or_create_subcategoria(db, categoria_obj, nombre_subcategoria_form)

            nuevo_sku = generar_siguiente_sku(db, categoria_obj) # categoria_obj ya está definido
            if not nuevo_sku:
                flash(f"No se pudo generar SKU para la categoría '{categoria_obj.nombre_categoria}'. Verifica la configuración de prefijos.", "danger")
                db.rollback()
                return render_template('crear_producto_unico.html',
                                       titulo_pagina="Crear Nuevo Producto",
                                       categorias_para_select=categorias_para_select,
                                       request_form_data=request_form_data_repopulate)

            producto_existente_sku = db.query(Producto).filter(Producto.sku == nuevo_sku).first()
            if producto_existente_sku:
                flash(f"El SKU generado '{nuevo_sku}' ya existe. Intenta de nuevo o revisa los contadores de SKU.", "danger")
                db.rollback()
                return render_template('crear_producto_unico.html',
                                       titulo_pagina="Crear Nuevo Producto",
                                       categorias_para_select=categorias_para_select,
                                       request_form_data=request_form_data_repopulate)

            datos_producto = {
                "nombre_producto": nombre_producto,
                "sku": nuevo_sku,
                "id_categoria_directa": categoria_obj.id_categoria if not subcategoria_obj else None,
                "id_subcategoria": subcategoria_obj.id_subcategoria if subcategoria_obj else None,
                "descripcion_adicional": request.form.get('descripcion_adicional'),
                "presentacion": request.form.get('presentacion'),
                "cantidad_por_presentacion": request.form.get('cantidad_por_presentacion'),
                "unidad_medida_venta": request.form.get('unidad_medida_venta'),
                "sabor": request.form.get('sabor'),
                "color": request.form.get('color'),
                "tamano_pulgadas": request.form.get('tamano_pulgadas'),
                "material": request.form.get('material'),
                "dimensiones_capacidad": request.form.get('dimensiones_capacidad'),
                "tema_estilo": request.form.get('tema_estilo'),
                "modalidad_servicio": request.form.get('modalidad_servicio'),
                "forma_tipo": request.form.get('forma_tipo'),
                "dias_anticipacion_compra": request.form.get('dias_anticipacion_compra', type=int) if request.form.get('dias_anticipacion_compra') else None,
                "activo": True
            }

            datos_producto_limpios = {k: v for k, v in datos_producto.items() if v is not None and v != ''}
            datos_producto_limpios["descripcion_completa_generada"] = construir_descripcion_completa(datos_producto_limpios)

            nuevo_producto_obj = Producto(**datos_producto_limpios)
            db.add(nuevo_producto_obj)
            db.commit()
            flash(f"Producto '{nuevo_producto_obj.nombre_producto}' (SKU: {nuevo_producto_obj.sku}) creado exitosamente.", "success")
            return redirect(url_for('vista_listar_productos'))

        # Para GET
        return render_template('crear_producto_unico.html',
                               titulo_pagina="Crear Nuevo Producto",
                               categorias_para_select=categorias_para_select, # Pasar la lista de nombres
                               request_form_data=request_form_data_repopulate)

    except ValueError as ve: # Capturar errores de conversión de tipo, etc.
        db.rollback()
        flash(f"Error de valor procesando el formulario: {ve}", "danger")
    except Exception as e: # Capturar cualquier otra excepción
        db.rollback()
        flash(f"Error general al crear el producto: {e}", "danger")
        print(f"Error creando producto: {e} ({type(e)})")
    finally:
        if db.is_active: # Asegurarse que la sesión esté activa antes de cerrarla
            db.close()
    
    # Si llegamos aquí (por error en POST o es un GET inicial después de un error), renderizar de nuevo con datos.
    return render_template('crear_producto_unico.html',
                           titulo_pagina="Crear Nuevo Producto",
                           categorias_para_select=categorias_para_select,
                           request_form_data=request_form_data_repopulate)


@app.route('/productos', methods=['GET'])
def vista_listar_productos():
    # ... (código existente sin cambios)
    db_session = SessionLocal()
    try:
        query, sort_by_param, sort_order_param = _construir_query_productos_filtrados(db_session, request.args)
        productos_db_raw = query.all()
        productos_enriquecidos = []
        for prod in productos_db_raw:
            info_precios = obtener_info_precios_producto(db_session, prod.id_producto)
            prod.info_precios = info_precios
            productos_enriquecidos.append(prod)
        categorias_db = db_session.query(Categoria).order_by(Categoria.nombre_categoria).all()
        subcategorias_db = db_session.query(Subcategoria).order_by(Subcategoria.nombre_subcategoria).all()
        sabores_db = [s[0] for s in db_session.query(Producto.sabor).distinct().filter(Producto.sabor != None, Producto.sabor != '').order_by(Producto.sabor).all()]
        colores_db = [c[0] for c in db_session.query(Producto.color).distinct().filter(Producto.color != None, Producto.color != '').order_by(Producto.color).all()]
        materiales_db = [m[0] for m in db_session.query(Producto.material).distinct().filter(Producto.material != None, Producto.material != '').order_by(Producto.material).all()]
        current_sort = {'by': sort_by_param, 'order': sort_order_param}
        current_filters = {
            'q': request.args.get('q', '').strip(),
            'categoria_id': request.args.get('categoria_id', type=int),
            'subcategoria_id': request.args.get('subcategoria_id', type=int),
            'sabor': request.args.get('sabor', '').strip(),
            'color': request.args.get('color', '').strip(),
            'material': request.args.get('material', '').strip()
        }
        sortable_columns_keys = ["id", "sku", "nombre", "categoria", "subcategoria", "presentacion", "activo"]
        return render_template('listar_productos.html',
                               productos=productos_enriquecidos,
                               titulo_pagina="Listado de Productos",
                               current_sort=current_sort,
                               sortable_column_keys=sortable_columns_keys,
                               categorias=categorias_db, subcategorias=subcategorias_db,
                               sabores=sabores_db, colores=colores_db, materiales=materiales_db,
                               current_filters=current_filters,
                               request_args=request.args,
                               aumento_mensual_est=PORCENTAJE_AUMENTO_MENSUAL_EST)
    except Exception as e:
        print(f"Error al obtener productos: {e}")
        flash(f"Error al cargar la lista de productos: {e}", "danger")
        return render_template('listar_productos.html', productos=[], titulo_pagina="Listado de Productos",
                               current_sort={}, sortable_column_keys=[],
                               categorias=[], subcategorias=[], sabores=[], colores=[], materiales=[], current_filters={}, request_args={},
                               aumento_mensual_est=PORCENTAJE_AUMENTO_MENSUAL_EST)
    finally:
        db_session.close()

# ... (resto de las rutas de app.py sin cambios) ...
@app.route('/productos/api/filtrar', methods=['GET'])
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
        sortable_columns_keys = ["id", "sku", "nombre", "categoria", "subcategoria", "presentacion", "activo"]
        return render_template('_tabla_productos_parcial.html',
                               productos=productos_enriquecidos_api,
                               current_sort=current_sort,
                               sortable_column_keys=sortable_columns_keys,
                               request_args=request.args,
                               aumento_mensual_est=PORCENTAJE_AUMENTO_MENSUAL_EST)
    except Exception as e:
        print(f"Error en API filtrar productos: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()

@app.route('/productos/api/buscar_por_descripcion', methods=['GET'])
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
                .filter(Producto.activo == True)\
                .limit(10)\
                .all()
        else:
             return jsonify([])
        resultados = []
        for prod in productos_encontrados:
            resultados.append({
                "id": prod.id_producto,
                "descripcion": prod.descripcion_completa_generada,
                "nombre": prod.nombre_producto,
                "sku": prod.sku,
                "presentacion": prod.presentacion,
                "unidad_medida_venta": prod.unidad_medida_venta
            })
        return jsonify(resultados)
    except Exception as e:
        print(f"Error en API buscar productos por descripción: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@app.route('/productos/<int:id_producto>/editar', methods=['GET', 'POST'])
def vista_editar_producto(id_producto):
    db = SessionLocal()
    try:
        producto_a_editar = get_producto_by_id_for_edit(db, id_producto)
        if not producto_a_editar:
            flash(f"Producto con ID {id_producto} no encontrado.", "danger")
            return redirect(url_for('vista_listar_productos'))
        if request.method == 'POST':
            datos_formulario = {
                "nombre_producto": request.form.get('nombre_producto'),
                "descripcion_adicional": request.form.get('descripcion_adicional'),
                "presentacion": request.form.get('presentacion'),
                "cantidad_por_presentacion": request.form.get('cantidad_por_presentacion'),
                "unidad_medida_venta": request.form.get('unidad_medida_venta'),
                "sabor": request.form.get('sabor'),
                "color": request.form.get('color'),
                "tamano_pulgadas": request.form.get('tamano_pulgadas'),
                "material": request.form.get('material'),
                "dimensiones_capacidad": request.form.get('dimensiones_capacidad'),
                "tema_estilo": request.form.get('tema_estilo'),
                "modalidad_servicio": request.form.get('modalidad_servicio'),
                "activo": request.form.get('activo'),
                "forma_tipo": request.form.get('forma_tipo'),
                "dias_anticipacion_compra": request.form.get('dias_anticipacion_compra', type=int)
            }
            datos_formulario["activo"] = True if datos_formulario["activo"] == 'on' else False
            datos_actualizacion = {k: v for k, v in datos_formulario.items() if v is not None or k == "activo"}
            try:
                update_producto_db(db, id_producto, datos_actualizacion)
                flash(f"Producto '{producto_a_editar.nombre_producto}' actualizado exitosamente.", "success")
                return redirect(url_for('vista_listar_productos'))
            except Exception as e:
                flash(f"Error al actualizar el producto: {e}", "danger")
        # Para GET, obtener todas las categorías y subcategorías para los selects (si los hubiera en el form de edición)
        # Actualmente el form de edición no permite cambiar categoría/subcategoría, así que esto es más para referencia
        categorias_db_form = db.query(Categoria).order_by(Categoria.nombre_categoria).all()
        subcategorias_db_form = db.query(Subcategoria).order_by(Subcategoria.nombre_subcategoria).all()
        return render_template('editar_producto.html',
                               titulo_pagina=f"Editar Producto: {producto_a_editar.nombre_producto}",
                               producto=producto_a_editar,
                               categorias=categorias_db_form, # Aunque no se usen para cambiar, pueden ser útiles para mostrar info
                               subcategorias=subcategorias_db_form)
    finally:
        if db.is_active:
            db.close()

@app.route('/proveedores', methods=['GET'])
def vista_listar_proveedores():
    db = SessionLocal()
    try:
        proveedores = db.query(Proveedor).order_by(Proveedor.nombre_proveedor).all()
        return render_template('listar_proveedores.html', proveedores=proveedores, titulo_pagina="Proveedores")
    finally:
        db.close()

@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
def vista_crear_proveedor():
    form_data = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        db = SessionLocal()
        try:
            nombre_prov = request.form.get('nombre_proveedor', '').strip()
            if not nombre_prov:
                flash("El nombre comercial del proveedor es obligatorio.", "danger")
                return render_template('crear_editar_proveedor.html', titulo_pagina="Nuevo Proveedor", proveedor=form_data)
            nuevo_proveedor = Proveedor(
                nombre_proveedor=nombre_prov,
                contacto_nombre=request.form.get('contacto_nombre'),
                telefono=request.form.get('telefono'),
                email=request.form.get('email'),
                direccion=request.form.get('direccion'),
                rfc=request.form.get('rfc', '').strip() or None,
                razon_social=request.form.get('razon_social', '').strip() or None,
                regimen_fiscal=request.form.get('regimen_fiscal', '').strip() or None,
                codigo_postal_fiscal=request.form.get('codigo_postal_fiscal', '').strip() or None,
                email_facturacion=request.form.get('email_facturacion', '').strip() or None,
                notas=request.form.get('notas'),
                activo=True
            )
            db.add(nuevo_proveedor)
            db.commit()
            flash(f"Proveedor '{nuevo_proveedor.nombre_proveedor}' creado exitosamente.", "success")
            return redirect(url_for('vista_listar_proveedores'))
        except sqlalchemy_exc.IntegrityError as ie:
            db.rollback()
            flash(f"Error de integridad al crear el proveedor: {ie}", "danger")
        except Exception as e:
            db.rollback()
            flash(f"Error al crear el proveedor: {e}", "danger")
        finally:
            if db.is_active:
                db.close()
    return render_template('crear_editar_proveedor.html', titulo_pagina="Nuevo Proveedor", proveedor=form_data)

@app.route('/proveedores/<int:id_proveedor>/editar', methods=['GET', 'POST'])
def vista_editar_proveedor(id_proveedor):
    db = SessionLocal()
    proveedor_a_editar = db.query(Proveedor).get(id_proveedor)
    try:
        if not proveedor_a_editar:
            flash("Proveedor no encontrado.", "danger")
            return redirect(url_for('vista_listar_proveedores'))
        if request.method == 'POST':
            nombre_prov_edit = request.form.get('nombre_proveedor', '').strip()
            if not nombre_prov_edit:
                flash("El nombre comercial del proveedor es obligatorio.", "danger")
                return render_template('crear_editar_proveedor.html', titulo_pagina="Editar Proveedor", proveedor=proveedor_a_editar)
            proveedor_a_editar.nombre_proveedor = nombre_prov_edit
            proveedor_a_editar.contacto_nombre = request.form.get('contacto_nombre')
            proveedor_a_editar.telefono = request.form.get('telefono')
            proveedor_a_editar.email = request.form.get('email')
            proveedor_a_editar.direccion = request.form.get('direccion')
            proveedor_a_editar.rfc = request.form.get('rfc', '').strip() or None
            proveedor_a_editar.razon_social = request.form.get('razon_social', '').strip() or None
            proveedor_a_editar.regimen_fiscal = request.form.get('regimen_fiscal', '').strip() or None
            proveedor_a_editar.codigo_postal_fiscal = request.form.get('codigo_postal_fiscal', '').strip() or None
            proveedor_a_editar.email_facturacion = request.form.get('email_facturacion', '').strip() or None
            proveedor_a_editar.notas = request.form.get('notas')
            db.commit()
            flash(f"Proveedor '{proveedor_a_editar.nombre_proveedor}' actualizado.", "success")
            return redirect(url_for('vista_listar_proveedores'))
        return render_template('crear_editar_proveedor.html', titulo_pagina="Editar Proveedor", proveedor=proveedor_a_editar)
    except sqlalchemy_exc.IntegrityError as ie:
        db.rollback()
        flash(f"Error de integridad al actualizar el proveedor: {ie}", "danger")
        return render_template('crear_editar_proveedor.html', titulo_pagina="Editar Proveedor", proveedor=proveedor_a_editar)
    except Exception as e:
        db.rollback()
        flash(f"Error al actualizar proveedor: {e}", "danger")
        return render_template('crear_editar_proveedor.html', titulo_pagina="Editar Proveedor", proveedor=proveedor_a_editar)
    finally:
        if db.is_active:
            db.close()

@app.route('/compras/registrar', methods=['GET', 'POST'])
def vista_registrar_compra():
    db = SessionLocal()
    try:
        if request.method == 'POST':
            try:
                fecha_documento_str = request.form.get('fecha_documento')
                id_proveedor = request.form.get('id_proveedor', type=int)
                numero_documento_form = request.form.get('numero_documento', '').strip() or None
                notas_generales_form = request.form.get('notas_generales', '').strip() or None

                detalles_data_from_form = []
                idx = 0
                while True:
                    id_prod_str = request.form.get(f'detalles[{idx}][id_producto]')
                    if id_prod_str is None: break
                    try:
                        id_producto_val = int(id_prod_str)
                        cantidad_val = float(request.form.get(f'detalles[{idx}][cantidad_comprada]', 0))
                        precio_orig_str = request.form.get(f'detalles[{idx}][precio_original_unitario]')
                        precio_original_val = float(precio_orig_str) if precio_orig_str and precio_orig_str.strip() else None
                        monto_desc_str = request.form.get(f'detalles[{idx}][monto_descuento_unitario]', '0')
                        monto_descuento_val = float(monto_desc_str) if monto_desc_str and monto_desc_str.strip() else 0.0
                        costo_neto_str = request.form.get(f'detalles[{idx}][costo_unitario_compra]')
                        costo_neto_val = float(costo_neto_str) if costo_neto_str and costo_neto_str.strip() else 0.0

                        if cantidad_val <= 0 or costo_neto_val <= 0:
                             flash(f"Error en ítem {idx+1}: Cantidad y Costo Neto deben ser mayores a cero.", "danger")
                             raise ValueError("Datos de ítem inválidos.")

                        detalle_actual = {
                            'id_producto': id_producto_val,
                            'cantidad_comprada': cantidad_val,
                            'precio_original_unitario': precio_original_val,
                            'monto_descuento_unitario': monto_descuento_val,
                            'costo_unitario_compra': costo_neto_val,
                            'unidad_compra': request.form.get(f'detalles[{idx}][unidad_compra]', 'Unidad'),
                            'disponibilidad_proveedor': request.form.get(f'detalles[{idx}][disponibilidad_proveedor]') or None,
                            'notas_item': request.form.get(f'detalles[{idx}][notas_item]') or None
                        }
                        detalles_data_from_form.append(detalle_actual)
                    except ValueError:
                        flash(f"Error en los datos numéricos del ítem {idx+1}. Verifica cantidad, precios y descuentos.", "danger")
                        raise ValueError("Datos numéricos de ítem inválidos.")
                    idx += 1

                if not detalles_data_from_form:
                    flash("Debes añadir al menos un producto a la compra.", "danger")
                    raise ValueError("No hay detalles de compra.")

                errores_encabezado = []
                if not fecha_documento_str: errores_encabezado.append("Fecha del documento es obligatoria.")
                if not id_proveedor: errores_encabezado.append("Proveedor es obligatorio.")

                fecha_documento = None
                if fecha_documento_str:
                    try: fecha_documento = date.fromisoformat(fecha_documento_str)
                    except ValueError: errores_encabezado.append("Formato de fecha inválido.")

                if errores_encabezado:
                    for error in errores_encabezado: flash(error, "danger")
                    raise ValueError("Errores de validación en el encabezado de la compra.")

                nuevo_encabezado = EncabezadoCompra(
                    id_proveedor=id_proveedor,
                    fecha_documento=fecha_documento,
                    numero_documento=numero_documento_form,
                    notas_generales=notas_generales_form,
                    monto_total_documento=0
                )
                db.add(nuevo_encabezado)

                monto_total_calculado = 0
                for item_data in detalles_data_from_form:
                    producto_seleccionado_item = db.query(Producto).get(item_data['id_producto'])
                    if not producto_seleccionado_item:
                        db.rollback()
                        flash(f"Producto con ID {item_data['id_producto']} no encontrado.", "danger")
                        raise ValueError("Producto de ítem no encontrado.")

                    costo_neto_item = item_data['costo_unitario_compra']
                    precio_original_a_guardar = item_data['precio_original_unitario']
                    if precio_original_a_guardar is None:
                        precio_original_a_guardar = costo_neto_item + item_data['monto_descuento_unitario']

                    costo_total_item_calc = item_data['cantidad_comprada'] * costo_neto_item
                    monto_total_calculado += costo_total_item_calc

                    nuevo_detalle = DetalleCompra(
                        encabezado=nuevo_encabezado,
                        id_producto=item_data['id_producto'],
                        cantidad_comprada=item_data['cantidad_comprada'],
                        unidad_compra=item_data['unidad_compra'],
                        precio_original_unitario=precio_original_a_guardar,
                        monto_descuento_unitario=item_data['monto_descuento_unitario'],
                        costo_unitario_compra=costo_neto_item,
                        costo_total_item=costo_total_item_calc,
                        disponibilidad_proveedor=item_data['disponibilidad_proveedor'],
                        notas_item=item_data['notas_item']
                    )
                    db.add(nuevo_detalle)

                    precio_prov = db.query(PrecioProveedor).filter_by(id_producto=item_data['id_producto'], id_proveedor=id_proveedor).first()
                    if precio_prov:
                        precio_prov.precio_compra = costo_neto_item
                        precio_prov.unidad_compra_proveedor = item_data['unidad_compra']
                        precio_prov.fecha_actualizacion_precio = fecha_documento
                    else:
                        nuevo_precio_prov = PrecioProveedor(
                            id_producto=item_data['id_producto'],
                            id_proveedor=id_proveedor,
                            precio_compra=costo_neto_item,
                            unidad_compra_proveedor=item_data['unidad_compra'],
                            fecha_actualizacion_precio=fecha_documento
                        )
                        db.add(nuevo_precio_prov)

                nuevo_encabezado.monto_total_documento = monto_total_calculado
                db.commit()
                flash(f"Compra registrada exitosamente (Factura/Nota ID: {nuevo_encabezado.id_encabezado_compra}).", "success")
                return redirect(url_for('vista_listar_facturas_compra'))

            except ValueError as ve:
                 pass
            except Exception as e:
                db.rollback()
                flash(f"Error al registrar la compra: {e}", "danger")
                print(f"Error registrando compra: {e} ({type(e)})")

        proveedores_form_get = db.query(Proveedor).filter_by(activo=True).order_by(Proveedor.nombre_proveedor).all()
        form_data_repopulate = request.form.to_dict() if request.method == 'POST' else {}
        if 'id_producto' in form_data_repopulate and \
           not form_data_repopulate.get('producto_descripcion_busqueda') and \
           form_data_repopulate['id_producto']:
            try:
                prod_id_for_repopulate = int(form_data_repopulate['id_producto'])
                prod_rep = db.query(Producto.descripcion_completa_generada).filter(Producto.id_producto == prod_id_for_repopulate).scalar_one_or_none()
                if prod_rep:
                    form_data_repopulate['producto_descripcion_busqueda'] = prod_rep
            except ValueError:
                pass

        return render_template('registrar_compra.html',
                               titulo_pagina="Registrar Nueva Compra",
                               proveedores=proveedores_form_get,
                               form_data=form_data_repopulate,
                               fecha_hoy=date.today().isoformat())
    finally:
        if db.is_active:
            db.close()

@app.route('/compras', methods=['GET'])
def vista_historial_compras():
    db = SessionLocal()
    try:
        detalles_de_compras = db.query(DetalleCompra)\
            .join(DetalleCompra.encabezado)\
            .join(DetalleCompra.producto)\
            .options(
                joinedload(DetalleCompra.producto),
                joinedload(DetalleCompra.encabezado).joinedload(EncabezadoCompra.proveedor)
            )\
            .order_by(desc(EncabezadoCompra.fecha_documento), desc(DetalleCompra.id_detalle_compra))\
            .all()
        return render_template('historial_compras.html',
                               compras=detalles_de_compras,
                               titulo_pagina="Historial de Compras por Producto")
    finally:
        if db.is_active:
            db.close()

@app.route('/compras/facturas', methods=['GET'])
def vista_listar_facturas_compra():
    db = SessionLocal()
    try:
        encabezados = db.query(EncabezadoCompra)\
            .options(joinedload(EncabezadoCompra.proveedor))\
            .order_by(desc(EncabezadoCompra.fecha_documento), desc(EncabezadoCompra.id_encabezado_compra))\
            .all()
        return render_template('listar_facturas_compra.html',
                               encabezados=encabezados,
                               titulo_pagina="Listado de Facturas/Notas de Compra")
    finally:
        if db.is_active:
            db.close()

@app.route('/proveedores/precios/cargar-manual', methods=['GET', 'POST'])
def vista_cargar_precios_manual():
    db = SessionLocal()
    try:
        if request.method == 'POST':
            id_proveedor_lp = request.form.get('id_proveedor_lp', type=int)
            fecha_vigencia_lp_str = request.form.get('fecha_vigencia_lp')
            if not id_proveedor_lp or not fecha_vigencia_lp_str:
                flash("Proveedor y Fecha de Vigencia son obligatorios.", "danger")
                raise ValueError("Faltan datos del encabezado de la lista de precios.")
            fecha_vigencia = date.fromisoformat(fecha_vigencia_lp_str)
            precios_data_from_form = []
            idx = 0
            while True:
                id_prod_str = request.form.get(f'precios[{idx}][id_producto]')
                if id_prod_str is None: break
                try:
                    precio_item_actual = {
                        'id_producto': int(id_prod_str),
                        'unidad_compra_proveedor': request.form.get(f'precios[{idx}][unidad_compra_proveedor]', '').strip(),
                        'precio_compra': float(request.form.get(f'precios[{idx}][precio_compra]', 0)),
                        'notas': request.form.get(f'precios[{idx}][notas]', '').strip() or None
                    }
                    if not precio_item_actual['unidad_compra_proveedor'] or precio_item_actual['precio_compra'] <= 0:
                        flash(f"Error en datos para producto ID {id_prod_str} (ítem {idx+1}). Unidad y precio son requeridos; precio debe ser positivo.", "warning")
                        idx += 1
                        continue
                    precios_data_from_form.append(precio_item_actual)
                except ValueError:
                    flash(f"Error en datos numéricos del ítem de precio {idx+1}.", "warning")
                    idx += 1
                    continue
                idx += 1
            if not precios_data_from_form:
                flash("No se añadieron precios válidos a la lista.", "warning")
            else:
                precios_actualizados = 0
                precios_creados = 0
                for precio_data in precios_data_from_form:
                    precio_existente = db.query(PrecioProveedor).filter_by(
                        id_proveedor=id_proveedor_lp,
                        id_producto=precio_data['id_producto']
                    ).first()
                    if precio_existente:
                        precio_existente.precio_compra = precio_data['precio_compra']
                        precio_existente.unidad_compra_proveedor = precio_data['unidad_compra_proveedor']
                        precio_existente.fecha_actualizacion_precio = fecha_vigencia
                        precio_existente.notas = precio_data['notas']
                        precios_actualizados += 1
                    else:
                        nuevo_precio = PrecioProveedor(
                            id_proveedor=id_proveedor_lp,
                            id_producto=precio_data['id_producto'],
                            precio_compra=precio_data['precio_compra'],
                            unidad_compra_proveedor=precio_data['unidad_compra_proveedor'],
                            fecha_actualizacion_precio=fecha_vigencia,
                            notas=precio_data['notas']
                        )
                        db.add(nuevo_precio)
                        precios_creados += 1
                db.commit()
                flash(f"Lista de precios guardada. {precios_creados} precios nuevos, {precios_actualizados} precios actualizados.", "success")
                return redirect(url_for('vista_cargar_precios_manual'))
        proveedores_form_get = db.query(Proveedor).filter_by(activo=True).order_by(Proveedor.nombre_proveedor).all()
        return render_template('cargar_precios_manual.html',
                               titulo_pagina="Cargar Lista de Precios Manualmente",
                               proveedores=proveedores_form_get,
                               form_data_lp=request.form if request.method == 'POST' else {},
                               fecha_hoy=date.today().isoformat())
    except ValueError as ve:
        proveedores_form_get = db.query(Proveedor).filter_by(activo=True).order_by(Proveedor.nombre_proveedor).all()
        return render_template('cargar_precios_manual.html',
                               titulo_pagina="Cargar Lista de Precios Manualmente",
                               proveedores=proveedores_form_get,
                               form_data_lp=request.form,
                               fecha_hoy=date.today().isoformat())
    except Exception as e:
        db.rollback()
        flash(f"Error al procesar la lista de precios: {e}", "danger")
        print(f"Error cargando precios: {e}")
        proveedores_form_get = db.query(Proveedor).filter_by(activo=True).order_by(Proveedor.nombre_proveedor).all()
        return render_template('cargar_precios_manual.html',
                               titulo_pagina="Cargar Lista de Precios Manualmente",
                               proveedores=proveedores_form_get,
                               form_data_lp=request.form if request.method == 'POST' else {},
                               fecha_hoy=date.today().isoformat())
    finally:
        if db.is_active:
            db.close()

@app.route('/proveedores/precios/cargar-csv', methods=['GET', 'POST'])
def vista_cargar_precios_csv():
    if request.method == 'POST':
        if 'archivo_csv_precios' not in request.files:
            flash('No se encontró la parte del archivo en la petición.', 'danger')
            return redirect(request.url)
        file = request.files['archivo_csv_precios']
        if file.filename == '':
            flash('Ningún archivo seleccionado.', 'warning')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            db_session = SessionLocal()
            try:
                resultado_parseo = parsear_y_validar_csv_precios(db_session, file.stream)
                session['precios_para_confirmar_csv'] = resultado_parseo.get("precios_listos", [])
                session['errores_parseo_precios_csv'] = resultado_parseo.get("errores", [])
                if not resultado_parseo.get("precios_listos") and not resultado_parseo.get("errores"):
                    flash("El archivo CSV de precios parece estar vacío o no se pudo parsear.", "warning")
                    return redirect(url_for('vista_cargar_precios_csv'))
                return redirect(url_for('vista_confirmar_carga_precios_csv'))
            except Exception as e_parse:
                flash(f"Error al parsear CSV de precios: {str(e_parse)}", "danger")
                print(f"Error parseando CSV precios: {e_parse}")
                return redirect(url_for('vista_cargar_precios_csv'))
            finally:
                db_session.close()
        else:
            flash('Tipo de archivo no permitido. Solo se permiten archivos .csv.', 'danger')
            return redirect(request.url)
    session.pop('precios_para_confirmar_csv', None)
    session.pop('errores_parseo_precios_csv', None)
    return render_template('cargar_precios_csv.html', titulo_pagina="Cargar Lista de Precios desde CSV")

@app.route('/proveedores/precios/confirmar-carga-csv', methods=['GET', 'POST'])
def vista_confirmar_carga_precios_csv():
    precios_para_confirmar = session.get('precios_para_confirmar_csv', [])
    errores_parseo = session.get('errores_parseo_precios_csv', [])
    if not precios_para_confirmar and not errores_parseo:
        flash("No hay datos de precios para confirmar. Por favor, sube un archivo CSV primero.", "warning")
        return redirect(url_for('vista_cargar_precios_csv'))
    if request.method == 'POST':
        if 'confirmar_precios' in request.form:
            db_session = SessionLocal()
            try:
                if precios_para_confirmar:
                    resultado_guardado = guardar_precios_en_bd(db_session, precios_para_confirmar)
                    flash(resultado_guardado.get("mensaje", "Proceso de guardado de precios finalizado."), 'info')
                else:
                    flash("No había precios válidos para guardar después del parseo.", "warning")
            except Exception as e:
                db_session.rollback()
                flash(f'Ocurrió un error crítico durante el guardado de precios: {str(e)}', 'danger')
            finally:
                db_session.close()
            session.pop('precios_para_confirmar_csv', None)
            session.pop('errores_parseo_precios_csv', None)
            return redirect(url_for('vista_cargar_precios_csv'))
        elif 'cancelar_precios' in request.form:
            flash("Carga de precios cancelada por el usuario.", "info")
            session.pop('precios_para_confirmar_csv', None)
            session.pop('errores_parseo_precios_csv', None)
            return redirect(url_for('vista_cargar_precios_csv'))
    return render_template('confirmar_carga_precios_csv.html',
                           titulo_pagina="Confirmar Carga de Precios desde CSV",
                           precios_para_confirmar=precios_para_confirmar,
                           errores_parseo_precios=errores_parseo)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
