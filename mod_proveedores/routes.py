# /mod_proveedores/routes.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy.orm import Session
from sqlalchemy import exc as sqlalchemy_exc
from decimal import Decimal
from datetime import date

from . import proveedores_bp # Importar el blueprint
from database import SessionLocal # Asumiendo que database.py está en el directorio raíz
from models import Proveedor, Producto, PrecioProveedor # Asumiendo que models.py está en el raíz
from utils_carga import parsear_y_validar_csv_precios, guardar_precios_en_bd # Y allowed_file si se usa aquí

# La función allowed_file es genérica, si solo se usa aquí, se puede definir aquí.
# Si se usa en múltiples blueprints, es mejor tenerla en un utils general o en el app principal.
# Por ahora, asumimos que está disponible (ej. importada desde app o un utils).
# from app import allowed_file # O desde donde esté definida

def allowed_file(filename): # Copiada aquí temporalmente, idealmente desde un utils
    ALLOWED_EXTENSIONS = {'csv'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- RUTAS PARA PROVEEDORES ---
@proveedores_bp.route('/', methods=['GET']) # Ruta base para /proveedores/
def vista_listar_proveedores():
    db = SessionLocal()
    try:
        proveedores = db.query(Proveedor).order_by(Proveedor.nombre_proveedor).all()
        return render_template('listar_proveedores.html',
                               proveedores=proveedores,
                               titulo_pagina="Listado de Proveedores")
    except Exception as e:
        flash(f"Error al cargar los proveedores: {str(e)}", "danger")
        return render_template('listar_proveedores.html', proveedores=[], titulo_pagina="Listado de Proveedores")
    finally:
        if db.is_active:
            db.close()

@proveedores_bp.route('/nuevo', methods=['GET', 'POST'])
def vista_crear_proveedor():
    if request.method == 'POST':
        db = SessionLocal()
        try:
            nombre_proveedor = request.form.get('nombre_proveedor', '').strip()
            if not nombre_proveedor:
                flash("El nombre comercial del proveedor es obligatorio.", "danger")
            else:
                nuevo_proveedor = Proveedor(
                    nombre_proveedor=nombre_proveedor,
                    contacto_nombre=request.form.get('contacto_nombre'),
                    telefono=request.form.get('telefono'),
                    email=request.form.get('email'),
                    direccion=request.form.get('direccion'),
                    razon_social=request.form.get('razon_social'),
                    rfc=request.form.get('rfc'),
                    regimen_fiscal=request.form.get('regimen_fiscal'),
                    codigo_postal_fiscal=request.form.get('codigo_postal_fiscal'),
                    email_facturacion=request.form.get('email_facturacion'),
                    notas=request.form.get('notas'),
                    activo=True # Por defecto activo
                )
                db.add(nuevo_proveedor)
                db.commit()
                flash(f"Proveedor '{nuevo_proveedor.nombre_proveedor}' creado exitosamente.", "success")
                return redirect(url_for('proveedores_bp.vista_listar_proveedores'))
        except sqlalchemy_exc.IntegrityError:
            if db.is_active: db.rollback()
            flash("Error: Ya existe un proveedor con ese nombre o RFC.", "danger")
        except Exception as e:
            if db.is_active: db.rollback()
            flash(f"Error al crear el proveedor: {str(e)}", "danger")
        finally:
            if db.is_active: db.close()
        return render_template('crear_editar_proveedor.html',
                               proveedor=request.form,
                               titulo_pagina="Nuevo Proveedor",
                               es_nuevo=True)

    return render_template('crear_editar_proveedor.html',
                           proveedor=None,
                           titulo_pagina="Nuevo Proveedor",
                           es_nuevo=True)

@proveedores_bp.route('/<int:id_proveedor>/editar', methods=['GET', 'POST'])
def vista_editar_proveedor(id_proveedor):
    db = SessionLocal()
    proveedor_a_editar = db.query(Proveedor).get(id_proveedor)
    if not proveedor_a_editar:
        flash("Proveedor no encontrado.", "danger")
        if db.is_active: db.close()
        return redirect(url_for('proveedores_bp.vista_listar_proveedores'))

    if request.method == 'POST':
        try:
            proveedor_a_editar.nombre_proveedor = request.form.get('nombre_proveedor', '').strip()
            if not proveedor_a_editar.nombre_proveedor:
                 flash("El nombre comercial del proveedor es obligatorio.", "danger")
            else:
                proveedor_a_editar.contacto_nombre = request.form.get('contacto_nombre')
                proveedor_a_editar.telefono = request.form.get('telefono')
                proveedor_a_editar.email = request.form.get('email')
                proveedor_a_editar.direccion = request.form.get('direccion')
                proveedor_a_editar.razon_social = request.form.get('razon_social')
                proveedor_a_editar.rfc = request.form.get('rfc')
                proveedor_a_editar.regimen_fiscal = request.form.get('regimen_fiscal')
                proveedor_a_editar.codigo_postal_fiscal = request.form.get('codigo_postal_fiscal')
                proveedor_a_editar.email_facturacion = request.form.get('email_facturacion')
                proveedor_a_editar.notas = request.form.get('notas')
                # proveedor_a_editar.activo = 'activo' in request.form # Si tienes un checkbox para 'activo'

                db.commit()
                flash(f"Proveedor '{proveedor_a_editar.nombre_proveedor}' actualizado.", "success")
                if db.is_active: db.close()
                return redirect(url_for('proveedores_bp.vista_listar_proveedores'))
        except Exception as e:
            if db.is_active: db.rollback()
            flash(f"Error al actualizar el proveedor: {str(e)}", "danger")
        # Si hay error, renderizar con datos del form (que están en el objeto)
        if db.is_active: db.close() # Cerrar antes de renderizar si no se hizo redirect
        return render_template('crear_editar_proveedor.html',
                               proveedor=proveedor_a_editar,
                               titulo_pagina=f"Editar Proveedor: {proveedor_a_editar.nombre_proveedor}",
                               es_nuevo=False)
    # Método GET
    if db.is_active: db.close()
    return render_template('crear_editar_proveedor.html',
                           proveedor=proveedor_a_editar,
                           titulo_pagina=f"Editar Proveedor: {proveedor_a_editar.nombre_proveedor}",
                           es_nuevo=False)

# --- RUTAS PARA PRECIOS DE PROVEEDOR (CSV y Manual) ---
@proveedores_bp.route('/precios/cargar-manual', methods=['GET', 'POST'])
def vista_cargar_precios_manual():
    db = SessionLocal()
    proveedores_activos = db.query(Proveedor).filter_by(activo=True).order_by(Proveedor.nombre_proveedor).all()
    form_data_lp = {}

    if request.method == 'POST':
        form_data_lp = request.form.to_dict(flat=False)
        id_proveedor_lp = request.form.get('id_proveedor_lp')
        fecha_vigencia_lp_str = request.form.get('fecha_vigencia_lp')
        # ... (resto de la lógica de POST de vista_cargar_precios_manual que tenías en app.py)
        notas_generales_lp = request.form.get('notas_generales_lp')
        precios_items = []
        idx = 0
        while f'precios[{idx}][id_producto]' in request.form:
            id_prod = request.form.get(f'precios[{idx}][id_producto]')
            unidad_compra = request.form.get(f'precios[{idx}][unidad_compra_proveedor]')
            precio = request.form.get(f'precios[{idx}][precio_compra]')
            notas_item = request.form.get(f'precios[{idx}][notas]')
            if id_prod and precio:
                precios_items.append({
                    'id_producto': int(id_prod),
                    'unidad_compra_proveedor': unidad_compra,
                    'precio_compra': Decimal(precio),
                    'notas': notas_item
                })
            idx += 1

        if not id_proveedor_lp or not fecha_vigencia_lp_str:
            flash("Proveedor y Fecha de Vigencia son obligatorios para la lista.", "danger")
        elif not precios_items:
            flash("Debes añadir al menos un precio a la lista.", "danger")
        else:
            try:
                fecha_vigencia_obj = date.fromisoformat(fecha_vigencia_lp_str)
                proveedor_obj = db.query(Proveedor).get(int(id_proveedor_lp))
                if not proveedor_obj:
                    flash("Proveedor seleccionado no válido.", "danger")
                else:
                    for item_precio_data in precios_items:
                        producto_obj = db.query(Producto).get(item_precio_data['id_producto'])
                        if not producto_obj:
                            flash(f"Producto con ID {item_precio_data['id_producto']} no encontrado. Se omite este precio.", "warning")
                            continue
                        precio_existente = db.query(PrecioProveedor).filter_by(
                            id_producto=producto_obj.id_producto,
                            id_proveedor=proveedor_obj.id_proveedor
                        ).first()
                        unidad_final = item_precio_data['unidad_compra_proveedor'] or producto_obj.presentacion_compra or "Unidad"
                        if precio_existente:
                            precio_existente.precio_compra = item_precio_data['precio_compra']
                            precio_existente.unidad_compra_proveedor = unidad_final
                            precio_existente.fecha_actualizacion_precio = fecha_vigencia_obj
                            precio_existente.notas = item_precio_data['notas']
                        else:
                            nuevo_precio = PrecioProveedor(
                                id_producto=producto_obj.id_producto,
                                id_proveedor=proveedor_obj.id_proveedor,
                                precio_compra=item_precio_data['precio_compra'],
                                unidad_compra_proveedor=unidad_final,
                                fecha_actualizacion_precio=fecha_vigencia_obj,
                                notas=item_precio_data['notas']
                            )
                            db.add(nuevo_precio)
                    db.commit()
                    flash(f"Lista de precios para '{proveedor_obj.nombre_proveedor}' guardada/actualizada exitosamente.", "success")
                    if db.is_active: db.close()
                    return redirect(url_for('proveedores_bp.vista_listar_proveedores'))
            except ValueError:
                if db.is_active: db.rollback()
                flash("Formato de fecha o número inválido.", "danger")
            except Exception as e:
                if db.is_active: db.rollback()
                flash(f"Error al guardar la lista de precios: {str(e)}", "danger")
        
        form_data_lp_repop = {
            'id_proveedor_lp': id_proveedor_lp,
            'fecha_vigencia_lp': fecha_vigencia_lp_str,
            'notas_generales_lp': notas_generales_lp,
            'precios': precios_items
        }
        if db.is_active: db.close()
        return render_template('cargar_precios_manual.html',
                               proveedores=proveedores_activos,
                               fecha_hoy=date.today().isoformat(),
                               form_data_lp=form_data_lp_repop,
                               titulo_pagina="Cargar Precios de Proveedor (Manual)")

    if db.is_active: db.close()
    return render_template('cargar_precios_manual.html',
                           proveedores=proveedores_activos,
                           fecha_hoy=date.today().isoformat(),
                           form_data_lp=form_data_lp,
                           titulo_pagina="Cargar Precios de Proveedor (Manual)")

@proveedores_bp.route('/precios/cargar-csv', methods=['GET', 'POST'])
def vista_cargar_precios_csv():
    if request.method == 'POST':
        if 'archivo_csv_precios' not in request.files:
            flash('No se encontró la parte del archivo en la petición.', 'danger')
            return redirect(request.url) # Debería ser url_for('proveedores_bp.vista_cargar_precios_csv')
        file = request.files['archivo_csv_precios']
        if file.filename == '':
            flash('Ningún archivo seleccionado.', 'warning')
            return redirect(url_for('proveedores_bp.vista_cargar_precios_csv'))
        if file and allowed_file(file.filename): # Usar la función allowed_file
            db_session_for_parse = SessionLocal()
            resultado_parseo = parsear_y_validar_csv_precios(db_session_for_parse, file.stream)
            db_session_for_parse.close()
            session['precios_para_confirmar_csv'] = resultado_parseo.get("precios_listos", [])
            session['errores_parseo_precios_csv'] = resultado_parseo.get("errores", [])
            if not resultado_parseo.get("precios_listos") and not resultado_parseo.get("errores"):
                flash("El archivo CSV de precios parece estar vacío o no se pudo parsear.", "warning")
                return redirect(url_for('proveedores_bp.vista_cargar_precios_csv'))
            return redirect(url_for('proveedores_bp.vista_confirmar_carga_precios_csv'))
        else:
            flash('Tipo de archivo no permitido. Solo se permiten archivos .csv.', 'danger')
            return redirect(url_for('proveedores_bp.vista_cargar_precios_csv'))

    session.pop('precios_para_confirmar_csv', None)
    session.pop('errores_parseo_precios_csv', None)
    return render_template('cargar_precios_csv.html', titulo_pagina="Cargar Precios desde CSV")

@proveedores_bp.route('/precios/confirmar-carga-csv', methods=['GET', 'POST'])
def vista_confirmar_carga_precios_csv():
    precios_para_confirmar = session.get('precios_para_confirmar_csv', [])
    errores_parseo = session.get('errores_parseo_precios_csv', [])
    if not precios_para_confirmar and not errores_parseo:
        flash("No hay datos de precios para confirmar. Por favor, sube un archivo CSV primero.", "warning")
        return redirect(url_for('proveedores_bp.vista_cargar_precios_csv'))

    if request.method == 'POST':
        db_session = SessionLocal()
        try:
            if 'confirmar' in request.form:
                if precios_para_confirmar:
                    resultado_guardado = guardar_precios_en_bd(db_session, precios_para_confirmar)
                    flash(resultado_guardado.get("mensaje", "Proceso de guardado de precios finalizado."), 'info')
                    if resultado_guardado.get("errores_detalle_guardado"):
                        for error in resultado_guardado.get("errores_detalle_guardado", []):
                            flash(error, 'danger')
                else:
                    flash("No había precios válidos para guardar después del parseo.", "warning")
            elif 'cancelar' in request.form:
                flash("Carga de precios cancelada por el usuario.", "info")
        except Exception as e:
            if db_session.is_active: db_session.rollback()
            flash(f'Ocurrió un error crítico durante el guardado de precios: {str(e)}', 'danger')
        finally:
            if db_session.is_active: db_session.close()
        session.pop('precios_para_confirmar_csv', None)
        session.pop('errores_parseo_precios_csv', None)
        return redirect(url_for('proveedores_bp.vista_listar_proveedores'))

    return render_template('confirmar_carga_precios_csv.html',
                           titulo_pagina="Confirmar Carga de Precios desde CSV",
                           precios=precios_para_confirmar,
                           errores=errores_parseo)
