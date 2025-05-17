# /mod_admin_servicios/routes.py
from flask import render_template, request, redirect, url_for, flash, session
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, distinct
from decimal import Decimal, InvalidOperation
from flask import jsonify

from . import admin_servicios_bp
from database import SessionLocal
from models import (
    TipoServicioBase, VarianteServicioConfig, GrupoComponenteConfig,
    OpcionComponenteServicio, Producto
)

# Función auxiliar para obtener los mensajes flash (si se usa para lógica condicional)
def get_flashed_messages_list():
    return session.get('_flashed_messages', [])


@admin_servicios_bp.route('/')
def admin_dashboard_servicios():
    # Renderiza el panel principal para la administración de servicios.
    return render_template('admin_dashboard_servicios.html', titulo_pagina="Catálogo de Servicios")

@admin_servicios_bp.route('/tipos-base', methods=['GET'])
def admin_vista_listar_tipos_servicio_base():
    # Muestra una lista de todos los Tipos de Servicio Base.
    db = SessionLocal()
    try:
        tipos_servicio = db.query(TipoServicioBase).order_by(TipoServicioBase.nombre).all()
        return render_template('listar_tipos_servicio_base.html',
                               tipos_servicio_base=tipos_servicio,
                               titulo_pagina="Tipos de Servicio Base")
    except Exception as e:
        flash(f"Error al cargar tipos de servicio: {str(e)}", "danger")
        return render_template('listar_tipos_servicio_base.html', tipos_servicio_base=[], titulo_pagina="Tipos de Servicio Base")
    finally:
        if db.is_active:
            db.close()

@admin_servicios_bp.route('/tipos-base/gestionar', methods=['GET', 'POST'])
@admin_servicios_bp.route('/tipos-base/<int:id_tipo_servicio_base>/gestionar', methods=['GET', 'POST'])
def admin_vista_crear_editar_tipo_servicio_base(id_tipo_servicio_base=None):
    # Permite crear un nuevo Tipo de Servicio Base o editar uno existente.
    db = SessionLocal()
    tipo_servicio_obj = None
    form_data_to_template = {} 
    es_nuevo = True
    try:
        if id_tipo_servicio_base:
            # Si se proporciona un ID, se está editando.
            tipo_servicio_obj = db.query(TipoServicioBase).get(id_tipo_servicio_base)
            if not tipo_servicio_obj:
                flash("Tipo de Servicio Base no encontrado.", "danger")
                return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))
            es_nuevo = False
            if request.method == 'GET':
                # Para GET, poblar el formulario con datos del objeto.
                form_data_to_template = {
                    'id_tipo_servicio_base': tipo_servicio_obj.id_tipo_servicio_base,
                    'nombre': tipo_servicio_obj.nombre,
                    'descripcion': tipo_servicio_obj.descripcion,
                    'activo': tipo_servicio_obj.activo
                }
        
        if request.method == 'POST':
            # Procesar los datos del formulario enviado.
            form_data_to_template = request.form.to_dict() 
            form_data_to_template['activo_submitted'] = '1' # Flag para saber si el checkbox fue enviado.
            form_data_to_template['activo'] = 'activo' in request.form # Valor del checkbox.
            
            nombre = request.form.get('nombre', '').strip()
            descripcion = request.form.get('descripcion', '').strip()
            activo_form_val = 'activo' in request.form
            
            has_validation_errors = False
            if not nombre:
                flash("El nombre del tipo de servicio es obligatorio.", "danger")
                has_validation_errors = True
            
            if not has_validation_errors: 
                if es_nuevo:
                    # Crear nuevo Tipo de Servicio Base.
                    existente = db.query(TipoServicioBase).filter(TipoServicioBase.nombre == nombre).first()
                    if existente:
                        flash(f"Ya existe un tipo de servicio con el nombre '{nombre}'.", "warning")
                    else:
                        tipo_servicio_obj_nuevo = TipoServicioBase(nombre=nombre, descripcion=descripcion, activo=activo_form_val)
                        db.add(tipo_servicio_obj_nuevo)
                        db.commit()
                        flash(f"Tipo de Servicio '{nombre}' creado exitosamente.", "success")
                        return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))
                elif tipo_servicio_obj: 
                    # Editar Tipo de Servicio Base existente.
                    tipo_servicio_obj.nombre = nombre
                    tipo_servicio_obj.descripcion = descripcion
                    tipo_servicio_obj.activo = activo_form_val
                    db.commit()
                    flash(f"Tipo de Servicio '{nombre}' actualizado exitosamente.", "success")
                    return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))
                else: 
                    flash("Error: Intentando editar un tipo de servicio no cargado.", "danger")
            
        # Determinar el título de la página.
        titulo_pagina_render = "Nuevo Tipo de Servicio Base"
        if not es_nuevo and tipo_servicio_obj: 
            nombre_actual_para_titulo = form_data_to_template.get('nombre') if request.method == 'POST' and form_data_to_template.get('nombre') else tipo_servicio_obj.nombre
            titulo_pagina_render = f"Editar Tipo: {nombre_actual_para_titulo}"

        return render_template('crear_editar_tipo_servicio_base.html',
                               tipo_servicio=form_data_to_template if request.method == 'POST' else (tipo_servicio_obj if tipo_servicio_obj else {}),
                               es_nuevo=es_nuevo,
                               titulo_pagina=titulo_pagina_render)
    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error en la gestión de Tipo de Servicio: {str(e)}", "danger")
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))
    finally:
        if db.is_active: db.close()

@admin_servicios_bp.route('/variantes/todas', methods=['GET'])
def admin_vista_listar_todas_variantes():
    # Muestra todas las Variantes de Servicio configuradas.
    db = SessionLocal()
    try:
        titulo = "Todas las Variantes de Servicio"
        query = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref) # Carga ansiosa del Tipo de Servicio Base.
        )
        variantes = query.order_by(
            VarianteServicioConfig.id_tipo_servicio_base,
            VarianteServicioConfig.nombre_variante
        ).all()
        tipos_servicio_base = db.query(TipoServicioBase).order_by(TipoServicioBase.nombre).all()
        return render_template('listar_variantes_servicio_config.html',
                               variantes_servicio_config=variantes,
                               tipo_servicio_base_asociado=None, # No se filtra por un tipo específico.
                               todos_tipos_servicio_base=tipos_servicio_base, # Para filtros futuros, si se añaden.
                               titulo_pagina=titulo)
    except Exception as e:
        flash(f"Error al cargar todas las variantes de servicio: {str(e)}", "danger")
        return redirect(url_for('admin_servicios_bp.admin_dashboard_servicios'))
    finally:
        if db.is_active: db.close()

@admin_servicios_bp.route('/tipos-base/<int:id_tipo_servicio_base>/variantes', methods=['GET'])
def admin_vista_listar_variantes_por_tipo(id_tipo_servicio_base):
    # Muestra las Variantes de Servicio para un Tipo de Servicio Base específico.
    db = SessionLocal()
    try:
        tipo_servicio_base_asociado = db.query(TipoServicioBase).get(id_tipo_servicio_base)
        if not tipo_servicio_base_asociado:
            flash("Tipo de Servicio Base no encontrado.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))

        query = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref)
        ).filter(VarianteServicioConfig.id_tipo_servicio_base == id_tipo_servicio_base)
        titulo = f"Variantes para: {tipo_servicio_base_asociado.nombre}"
        variantes = query.order_by(VarianteServicioConfig.nombre_variante).all()
        return render_template('listar_variantes_servicio_config.html',
                               variantes_servicio_config=variantes,
                               tipo_servicio_base_asociado=tipo_servicio_base_asociado,
                               todos_tipos_servicio_base=None, # No es necesario aquí.
                               titulo_pagina=titulo)
    except Exception as e:
        flash(f"Error al cargar variantes para el tipo de servicio: {str(e)}", "danger")
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))
    finally:
        if db.is_active: db.close()

@admin_servicios_bp.route('/variantes/gestionar', methods=['GET', 'POST'])
@admin_servicios_bp.route('/variantes/gestionar/tipo/<int:id_tipo_servicio_base_preseleccionado>', methods=['GET', 'POST'])
@admin_servicios_bp.route('/variantes/<int:id_variante_config>/gestionar', methods=['GET', 'POST'])
def admin_vista_crear_editar_variante_config(id_variante_config=None, id_tipo_servicio_base_preseleccionado=None):
    # Permite crear o editar una Variante de Servicio.
    db = SessionLocal()
    variante_config_obj = None
    variante_config_form_data = {} 
    es_nuevo = True
    todos_tipos_base_render = [] 
    try:
        if id_variante_config: 
            # Editando una variante existente.
            variante_config_obj = db.query(VarianteServicioConfig).options(
                joinedload(VarianteServicioConfig.tipo_servicio_base_ref),
                selectinload(VarianteServicioConfig.grupos_componentes) # Cargar grupos para la vista de edición.
            ).get(id_variante_config)
            if not variante_config_obj:
                flash("Variante de Servicio no encontrada.", "danger")
                return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
            es_nuevo = False
            id_tipo_servicio_base_preseleccionado = variante_config_obj.id_tipo_servicio_base
            if request.method == 'GET':
                # Poblar el formulario con datos del objeto.
                variante_config_form_data = {
                    'id_tipo_servicio_base': variante_config_obj.id_tipo_servicio_base,
                    'nivel_paquete': variante_config_obj.nivel_paquete or '',
                    'nivel_perfil': variante_config_obj.nivel_perfil or '',
                    'codigo_identificador_variante': variante_config_obj.codigo_identificador_variante or '',
                    'precio_base_sugerido': '{:.2f}'.format(variante_config_obj.precio_base_sugerido) if variante_config_obj.precio_base_sugerido is not None else '',
                    'descripcion_publica': variante_config_obj.descripcion_publica or '',
                    'cantidad_base_por_invitado': '{:.3f}'.format(variante_config_obj.cantidad_base_por_invitado) if variante_config_obj.cantidad_base_por_invitado is not None else '',
                    'unidad_medida_servicio_por_invitado': variante_config_obj.unidad_medida_servicio_por_invitado or '',
                    'cantidad_base_fija_servicio': '{:.2f}'.format(variante_config_obj.cantidad_base_fija_servicio) if variante_config_obj.cantidad_base_fija_servicio is not None else '',
                    'activo': variante_config_obj.activo
                }
        elif request.method == 'GET' and id_tipo_servicio_base_preseleccionado:
            # Creando una nueva variante con un tipo base preseleccionado.
            variante_config_form_data = {'id_tipo_servicio_base': str(id_tipo_servicio_base_preseleccionado)}

        if request.method == 'POST':
            # Procesar datos del formulario.
            variante_config_form_data = request.form.to_dict()
            id_tipo_base_form = request.form.get('id_tipo_servicio_base', type=int)
            nivel_paquete_form = request.form.get('nivel_paquete', '').strip()
            nivel_perfil_form = request.form.get('nivel_perfil', '').strip()
            
            codigo_identificador_form = request.form.get('codigo_identificador_variante', '').strip() or None
            precio_base_str = request.form.get('precio_base_sugerido')
            precio_base_form = None
            if precio_base_str and precio_base_str.strip():
                try: precio_base_form = Decimal(precio_base_str)
                except InvalidOperation: flash("Precio base sugerido tiene un formato numérico inválido.", "danger")

            descripcion_publica_form = request.form.get('descripcion_publica', '').strip()
            
            cant_base_inv_str = request.form.get('cantidad_base_por_invitado')
            cant_base_inv_form = None
            if cant_base_inv_str and cant_base_inv_str.strip():
                try: cant_base_inv_form = Decimal(cant_base_inv_str)
                except InvalidOperation: flash("Cantidad base por invitado tiene un formato numérico inválido.", "danger")

            unidad_med_serv_inv_form = request.form.get('unidad_medida_servicio_por_invitado', '').strip() or None
            
            cant_base_fija_str = request.form.get('cantidad_base_fija_servicio')
            cant_base_fija_form = None
            if cant_base_fija_str and cant_base_fija_str.strip():
                try: cant_base_fija_form = Decimal(cant_base_fija_str)
                except InvalidOperation: flash("Cantidad base fija tiene un formato numérico inválido.", "danger")
            
            activo_form = 'activo' in request.form

            # Validaciones
            has_validation_errors = False
            if not id_tipo_base_form: flash("Tipo de Servicio Base es obligatorio.", "danger"); has_validation_errors = True
            if not nivel_paquete_form: flash("Nivel de Paquete es obligatorio.", "danger"); has_validation_errors = True
            if not nivel_perfil_form: flash("Nivel de Perfil es obligatorio.", "danger"); has_validation_errors = True
            if get_flashed_messages_list() and any("formato numérico inválido" in msg[1] for msg in get_flashed_messages_list()): # Chequear si hubo error de conversión de Decimal
                has_validation_errors = True
            
            tipo_base_obj = None
            if id_tipo_base_form: 
                tipo_base_obj = db.query(TipoServicioBase).get(id_tipo_base_form)
                if not tipo_base_obj:
                    flash("Tipo de Servicio Base seleccionado no es válido.", "danger")
                    has_validation_errors = True
            
            if not has_validation_errors and tipo_base_obj:
                # Generar nombre de variante.
                partes_nombre = [tipo_base_obj.nombre]
                if nivel_paquete_form: partes_nombre.append(nivel_paquete_form)
                if nivel_perfil_form: partes_nombre.append(nivel_perfil_form)
                nombre_variante_generado = " - ".join(partes_nombre)

                if es_nuevo:
                    # Crear nueva variante.
                    existente = db.query(VarianteServicioConfig).filter(
                        VarianteServicioConfig.id_tipo_servicio_base == id_tipo_base_form,
                        VarianteServicioConfig.nombre_variante == nombre_variante_generado
                    ).first()
                    if existente:
                         flash(f"Ya existe una variante con la combinación: '{nombre_variante_generado}'.", "warning")
                    else:
                        nueva_variante_obj = VarianteServicioConfig(
                            id_tipo_servicio_base=id_tipo_base_form,
                            nombre_variante=nombre_variante_generado,
                            nivel_paquete=nivel_paquete_form,
                            nivel_perfil=nivel_perfil_form,
                            codigo_identificador_variante=codigo_identificador_form,
                            precio_base_sugerido=precio_base_form,
                            descripcion_publica=descripcion_publica_form,
                            cantidad_base_por_invitado=cant_base_inv_form,
                            unidad_medida_servicio_por_invitado=unidad_med_serv_inv_form,
                            cantidad_base_fija_servicio=cant_base_fija_form,
                            activo=activo_form
                        )
                        db.add(nueva_variante_obj)
                        db.commit() 
                        db.refresh(nueva_variante_obj) 
                        id_nueva_variante_para_redirect = nueva_variante_obj.id_variante_config
                        flash(f"Variante '{nombre_variante_generado}' creada. ID: {id_nueva_variante_para_redirect}. Ahora puedes configurar sus grupos y opciones.", "success")
                        return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_nueva_variante_para_redirect))
                elif variante_config_obj: 
                    # Editar variante existente.
                    if (variante_config_obj.nombre_variante != nombre_variante_generado):
                        existente_otro = db.query(VarianteServicioConfig).filter(
                            VarianteServicioConfig.id_tipo_servicio_base == id_tipo_base_form, # El tipo base no cambia al editar
                            VarianteServicioConfig.nombre_variante == nombre_variante_generado,
                            VarianteServicioConfig.id_variante_config != id_variante_config # Excluir la variante actual
                        ).first()
                        if existente_otro:
                            flash(f"Ya existe otra variante con la combinación: '{nombre_variante_generado}'.", "warning")
                    
                    if not get_flashed_messages_list() or not any("Ya existe otra variante" in msg[1] for msg in get_flashed_messages_list()): 
                        variante_config_obj.nombre_variante = nombre_variante_generado
                        variante_config_obj.nivel_paquete = nivel_paquete_form
                        variante_config_obj.nivel_perfil = nivel_perfil_form
                        variante_config_obj.codigo_identificador_variante = codigo_identificador_form
                        variante_config_obj.precio_base_sugerido = precio_base_form
                        variante_config_obj.descripcion_publica = descripcion_publica_form
                        variante_config_obj.cantidad_base_por_invitado = cant_base_inv_form
                        variante_config_obj.unidad_medida_servicio_por_invitado = unidad_med_serv_inv_form
                        variante_config_obj.cantidad_base_fija_servicio = cant_base_fija_form
                        variante_config_obj.activo = activo_form
                        db.commit()
                        db.refresh(variante_config_obj)
                        flash(f"Variante '{nombre_variante_generado}' actualizada.", "success")
                        # No redirigir aquí para permitir ver los mensajes flash y continuar editando grupos/opciones.
                        # return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_variante_config))
        
        # Para GET o si POST tuvo errores y se necesita repopular.
        todos_tipos_base_render = db.query(TipoServicioBase).filter_by(activo=True).order_by(TipoServicioBase.nombre).all()
        titulo_pagina_render = "Nueva Variante de Servicio"
        if variante_config_obj: 
            nombre_para_titulo = variante_config_obj.nombre_variante # Usar el nombre ya actualizado si es POST
            if request.method == 'POST' and variante_config_form_data.get('nombre_variante'): # Si el nombre se generó en el POST
                 nombre_para_titulo = variante_config_form_data.get('nombre_variante')
            elif request.method == 'GET' and variante_config_form_data.get('nombre_variante'): # Si se está cargando desde form_data
                 nombre_para_titulo = variante_config_form_data.get('nombre_variante')

            titulo_pagina_render = f"Editar Variante: {nombre_para_titulo}"
            if variante_config_obj.tipo_servicio_base_ref:
                 titulo_pagina_render += f" (Tipo: {variante_config_obj.tipo_servicio_base_ref.nombre})"
        elif id_tipo_servicio_base_preseleccionado and es_nuevo: 
             tipo_base_sel_obj = db.query(TipoServicioBase).get(id_tipo_servicio_base_preseleccionado)
             if tipo_base_sel_obj:
                titulo_pagina_render = f"Nueva Variante para: {tipo_base_sel_obj.nombre}"
        
        return render_template('crear_editar_variante_servicio_config.html',
                               variante_config_form_data=variante_config_form_data, # Usar datos del form si es POST
                               variante_config_obj=variante_config_obj, # Objeto original para referencia
                               es_nuevo=es_nuevo,
                               todos_tipos_servicio_base=todos_tipos_base_render,
                               id_tipo_servicio_base_preseleccionado=id_tipo_servicio_base_preseleccionado,
                               titulo_pagina=titulo_pagina_render)

    except InvalidOperation as ioe: 
        if db.is_active: db.rollback()
        flash(f"Error en formato numérico: {str(ioe)}", "danger")
        # Repopular con los datos del formulario que causaron el error.
        todos_tipos_base_render = db.query(TipoServicioBase).filter_by(activo=True).order_by(TipoServicioBase.nombre).all()
        titulo_pagina_render = "Revisar Datos de Variante"
        # Si variante_config_obj existe (estamos editando), pasarlo para la estructura de la página.
        # Si es nuevo, variante_config_obj será None.
        return render_template('crear_editar_variante_servicio_config.html',
                           variante_config_form_data=request.form.to_dict() if request.method == 'POST' else variante_config_form_data,
                           variante_config_obj=variante_config_obj,
                           es_nuevo=es_nuevo,
                           todos_tipos_servicio_base=todos_tipos_base_render,
                           id_tipo_servicio_base_preseleccionado=id_tipo_servicio_base_preseleccionado,
                           titulo_pagina=titulo_pagina_render)
    except Exception as e: 
        if db.is_active: db.rollback()
        flash(f"Error al procesar la Variante de Servicio: {str(e)}", "danger")
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
    finally:
        if db.is_active: db.close()


@admin_servicios_bp.route('/variantes/<int:id_variante_config>/detalle', methods=['GET'])
def admin_vista_detalle_variante_config(id_variante_config):
    # Muestra los detalles de una Variante de Servicio, incluyendo sus grupos y opciones.
    db = SessionLocal()
    try:
        variante_config = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref),
            joinedload(VarianteServicioConfig.grupos_componentes) # Carga ansiosa de grupos.
                .selectinload(GrupoComponenteConfig.opciones_componente_disponibles) # Y de cada grupo, sus opciones.
                .selectinload(OpcionComponenteServicio.producto_interno_ref) # Y de cada opción, su producto interno.
        ).get(id_variante_config)
        if not variante_config:
            flash("Variante de Servicio no encontrada.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
        
        titulo = f"Detalle Variante: {variante_config.nombre_variante}"
        return render_template('detalle_variante_servicio_config.html',
                               variante_config=variante_config,
                               titulo_pagina=titulo)
    finally:
        if db.is_active: db.close()


@admin_servicios_bp.route('/variantes/<int:id_variante_config>/grupos/nuevo', methods=['GET', 'POST'])
def admin_vista_crear_grupo_componente(id_variante_config):
    # Permite crear un nuevo Grupo de Componentes para una Variante de Servicio.
    db = SessionLocal()
    try:
        variante_config = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref) # Cargar tipo base para mostrar en el título.
        ).get(id_variante_config)

        if not variante_config:
            flash("Variante de Servicio no encontrada para añadirle un grupo.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))

        form_values = {} 
        if request.method == 'POST':
            form_values = request.form.to_dict()
            nombre_grupo = request.form.get('nombre_grupo', '').strip()
            
            has_validation_errors = False
            if not nombre_grupo:
                flash("El nombre del grupo es obligatorio.", "danger")
                has_validation_errors = True
            
            cantidad_opciones = 1
            orden_display = 0
            porcentaje_servicio = None
            try:
                cantidad_opciones_str = request.form.get('cantidad_opciones_seleccionables', '1')
                cantidad_opciones = int(cantidad_opciones_str) if cantidad_opciones_str.strip() else 1
                if cantidad_opciones < 0: # Permitir 0 si significa "seleccionar todos los disponibles" (lógica a implementar si es necesario)
                    flash("La cantidad de opciones seleccionables no puede ser negativa.", "danger")
                    has_validation_errors = True
                
                orden_display_str = request.form.get('orden_display', '0')
                orden_display = int(orden_display_str) if orden_display_str.strip() else 0
                if orden_display < 0:
                    flash("El orden de visualización no puede ser negativo.", "danger")
                    has_validation_errors = True

                porcentaje_str = request.form.get('porcentaje_del_total_servicio')
                if porcentaje_str and porcentaje_str.strip():
                    porcentaje_decimal = Decimal(porcentaje_str)
                    if not (0 <= porcentaje_decimal <= 100):
                        flash("El porcentaje debe estar entre 0 y 100.", "danger")
                        has_validation_errors = True
                    else:
                        porcentaje_servicio = porcentaje_decimal / Decimal(100) # Guardar como fracción (0.0 a 1.0)
            except (ValueError, InvalidOperation):
                flash("Cantidad de opciones, orden y porcentaje deben ser números válidos y no negativos (porcentaje entre 0-100).", "danger")
                has_validation_errors = True
            
            if not has_validation_errors:
                grupo_existente = db.query(GrupoComponenteConfig).filter_by(
                    id_variante_config=id_variante_config,
                    nombre_grupo=nombre_grupo
                ).first()
                if grupo_existente:
                    flash(f"Ya existe un grupo llamado '{nombre_grupo}' para esta variante.", "warning")
                else:
                    nuevo_grupo = GrupoComponenteConfig(
                        id_variante_config=id_variante_config,
                        nombre_grupo=nombre_grupo,
                        cantidad_opciones_seleccionables=cantidad_opciones,
                        orden_display=orden_display,
                        porcentaje_del_total_servicio=porcentaje_servicio
                    )
                    db.add(nuevo_grupo)
                    db.commit()
                    flash(f"Grupo '{nombre_grupo}' añadido exitosamente a la variante '{variante_config.nombre_variante}'.", "success")
                    # Redirigir a la edición de la variante para que pueda ver el nuevo grupo y añadirle opciones.
                    return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_variante_config))
        
        # Para GET o si POST tuvo errores.
        return render_template('crear_editar_grupo_componente.html',
                               variante_config=variante_config,
                               grupo_config_original=None, 
                               form_values=form_values, # Repopular con datos del POST si hubo error.
                               es_nuevo=True,
                               titulo_pagina=f"Nuevo Grupo para: {variante_config.nombre_variante}")
    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error al procesar la creación del grupo: {str(e)}", "danger")
        if id_variante_config:
            return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_variante_config))
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
    finally:
        if db.is_active: db.close()


@admin_servicios_bp.route('/grupos/<int:id_grupo_config>/editar', methods=['GET', 'POST'])
def admin_vista_editar_grupo_componente(id_grupo_config):
    # Permite editar un Grupo de Componentes existente.
    db = SessionLocal()
    grupo_config_obj = None 
    variante_config_obj = None # Para pasar a la plantilla.
    form_values = {} # Para repopular el formulario.

    try:
        grupo_config_obj = db.query(GrupoComponenteConfig).options(
            joinedload(GrupoComponenteConfig.variante_servicio_config_ref) # Cargar la variante padre.
                .joinedload(VarianteServicioConfig.tipo_servicio_base_ref) # Y el tipo de servicio de la variante.
        ).get(id_grupo_config)

        if not grupo_config_obj:
            flash("Grupo de Componentes no encontrado.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
        
        variante_config_obj = grupo_config_obj.variante_servicio_config_ref # Referencia a la variante padre.
        
        if request.method == 'GET':
            # Para GET, poblar el formulario con datos del objeto.
            porcentaje_display_val = ''
            if grupo_config_obj.porcentaje_del_total_servicio is not None:
                try:
                    # Mostrar como porcentaje (ej. 30.00) en lugar de fracción (0.30)
                    porcentaje_display_val = "{:.2f}".format(float(grupo_config_obj.porcentaje_del_total_servicio) * 100)
                except (TypeError, ValueError): 
                    porcentaje_display_val = '' 
            
            form_values = {
                'nombre_grupo': grupo_config_obj.nombre_grupo,
                'cantidad_opciones_seleccionables': grupo_config_obj.cantidad_opciones_seleccionables,
                'orden_display': grupo_config_obj.orden_display,
                'porcentaje_del_total_servicio': porcentaje_display_val
            }

        if request.method == 'POST':
            form_values = request.form.to_dict() # Tomar datos del form para repopular si hay error.
            nombre_grupo_form = request.form.get('nombre_grupo', '').strip()
            
            has_validation_errors = False
            if not nombre_grupo_form:
                flash("El nombre del grupo es obligatorio.", "danger")
                has_validation_errors = True
            
            # Inicializar con valores del objeto para evitar errores si el form no los envía todos
            cantidad_opciones_form = grupo_config_obj.cantidad_opciones_seleccionables
            orden_display_form = grupo_config_obj.orden_display
            porcentaje_servicio_form = grupo_config_obj.porcentaje_del_total_servicio

            try:
                cantidad_opciones_form_str = request.form.get('cantidad_opciones_seleccionables')
                if cantidad_opciones_form_str is not None and cantidad_opciones_form_str.strip():
                    cantidad_opciones_form = int(cantidad_opciones_form_str)
                    if cantidad_opciones_form < 0:
                        flash("La cantidad de opciones no puede ser negativa.", "danger")
                        has_validation_errors = True
                
                orden_display_str = request.form.get('orden_display')
                if orden_display_str is not None and orden_display_str.strip(): 
                    orden_display_form = int(orden_display_str)
                    if orden_display_form < 0:
                        flash("El orden no puede ser negativo.", "danger")
                        has_validation_errors = True
                elif orden_display_str == '': # Si se envía vacío, se interpreta como 0 o el valor actual.
                     orden_display_form = 0 # O mantener grupo_config_obj.orden_display


                porcentaje_str_form = request.form.get('porcentaje_del_total_servicio')
                if porcentaje_str_form is not None: 
                    if porcentaje_str_form.strip(): 
                        porcentaje_decimal_form = Decimal(porcentaje_str_form) 
                        if not (0 <= porcentaje_decimal_form <= 100):
                            flash("El porcentaje debe estar entre 0 y 100.", "danger")
                            has_validation_errors = True
                        else:
                            porcentaje_servicio_form = porcentaje_decimal_form / Decimal(100) # Guardar como fracción
                    else: # Si el campo se envía vacío, significa que no hay porcentaje.
                        porcentaje_servicio_form = None 
            except (ValueError, InvalidOperation): 
                flash("Cantidad, orden y porcentaje deben ser números válidos y no negativos (porcentaje 0-100).", "danger")
                has_validation_errors = True
            
            if not has_validation_errors:
                # Validar unicidad del nombre del grupo DENTRO de la misma variante, excluyendo el grupo actual.
                if grupo_config_obj.nombre_grupo != nombre_grupo_form:
                    grupo_existente = db.query(GrupoComponenteConfig).filter(
                        GrupoComponenteConfig.id_variante_config == variante_config_obj.id_variante_config,
                        GrupoComponenteConfig.nombre_grupo == nombre_grupo_form,
                        GrupoComponenteConfig.id_grupo_config != id_grupo_config # Excluir el propio grupo.
                    ).first()
                    if grupo_existente:
                        flash(f"Ya existe otro grupo llamado '{nombre_grupo_form}' para esta variante.", "warning")
                        has_validation_errors = True 
                
                if not has_validation_errors: # Si no hubo error de unicidad.
                    grupo_config_obj.nombre_grupo = nombre_grupo_form
                    grupo_config_obj.cantidad_opciones_seleccionables = cantidad_opciones_form
                    grupo_config_obj.orden_display = orden_display_form
                    grupo_config_obj.porcentaje_del_total_servicio = porcentaje_servicio_form
                    db.commit()
                    flash(f"Grupo '{grupo_config_obj.nombre_grupo}' actualizado exitosamente.", "success")
                    # Redirigir a la edición de la variante padre.
                    return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=variante_config_obj.id_variante_config))
        
        # Para GET o si POST tuvo errores, renderizar la plantilla.
        return render_template('crear_editar_grupo_componente.html',
                               variante_config=variante_config_obj, 
                               grupo_config_original=grupo_config_obj, 
                               form_values=form_values, # Contiene datos del GET o del POST fallido.
                               es_nuevo=False,
                               titulo_pagina=f"Editar Grupo: {grupo_config_obj.nombre_grupo}")
    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error al procesar la edición del grupo: {str(e)}", "danger")
        # Determinar a dónde redirigir en caso de error.
        id_var_fallback = None
        if variante_config_obj and hasattr(variante_config_obj, 'id_variante_config'):
             id_var_fallback = variante_config_obj.id_variante_config
        elif grupo_config_obj and hasattr(grupo_config_obj, 'id_variante_config'): 
            id_var_fallback = grupo_config_obj.id_variante_config
        
        if id_var_fallback:
             return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_var_fallback))
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes')) # Fallback genérico.
    finally:
        if db.is_active: db.close()


@admin_servicios_bp.route('/variantes/<int:id_variante_config>/grupos/<int:id_grupo_config>/opciones', methods=['GET', 'POST'])
def admin_vista_gestionar_opciones_componente(id_variante_config, id_grupo_config):
    # Permite añadir, ver y eliminar Opciones de Componente para un Grupo específico.
    db = SessionLocal()
    try:
        grupo_config = db.query(GrupoComponenteConfig).options(
            joinedload(GrupoComponenteConfig.variante_servicio_config_ref).joinedload(VarianteServicioConfig.tipo_servicio_base_ref), # Cargar variante y su tipo base.
            selectinload(GrupoComponenteConfig.opciones_componente_disponibles).joinedload(OpcionComponenteServicio.producto_interno_ref) # Cargar opciones y sus productos.
        ).filter_by(id_grupo_config=id_grupo_config, id_variante_config=id_variante_config).first()

        if not grupo_config:
            flash("Grupo de Componentes no encontrado o no pertenece a la variante especificada.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_variante_config))

        if request.method == 'POST':
            accion = request.form.get('accion')
            
            if accion == 'crear_opcion':
                # Lógica para crear una nueva opción.
                id_producto_interno_str = request.form.get('id_producto_interno')
                id_producto_interno_form = int(id_producto_interno_str) if id_producto_interno_str and id_producto_interno_str.isdigit() else None
                
                nombre_display_cliente = request.form.get('nombre_display_cliente', '').strip()
                cantidad_consumo_base_str = request.form.get('cantidad_consumo_base')
                unidad_consumo_base = request.form.get('unidad_consumo_base', '').strip()
                costo_adicional_opcion_str = request.form.get('costo_adicional_opcion')
                descripcion_display_cliente = request.form.get('descripcion_display_cliente', '').strip()
                opcion_activa = 'opcion_activa' in request.form

                has_option_errors = False
                if not nombre_display_cliente:
                    flash("El Nombre para Mostrar al Cliente es obligatorio.", "danger")
                    has_option_errors = True
                if not cantidad_consumo_base_str or not cantidad_consumo_base_str.strip() or not unidad_consumo_base:
                    flash("Cantidad y Unidad de Consumo Base son obligatorias.", "danger")
                    has_option_errors = True
                
                cantidad_consumo_base_dec = None
                costo_adicional_opcion_dec = Decimal('0.00')

                try:
                    if cantidad_consumo_base_str and cantidad_consumo_base_str.strip(): 
                        cantidad_consumo_base_dec = Decimal(cantidad_consumo_base_str)
                        if cantidad_consumo_base_dec <= 0:
                            flash("La Cantidad de Consumo Base debe ser mayor a cero.", "danger")
                            has_option_errors = True
                    elif not has_option_errors: # Si no hubo error previo pero el campo está vacío.
                        flash("Cantidad de Consumo Base es obligatoria y debe ser mayor a cero.", "danger")
                        has_option_errors = True

                    if costo_adicional_opcion_str and costo_adicional_opcion_str.strip():
                        costo_adicional_opcion_dec = Decimal(costo_adicional_opcion_str)
                        if costo_adicional_opcion_dec < 0:
                            flash("El Costo Adicional no puede ser negativo.", "danger")
                            has_option_errors = True
                except InvalidOperation:
                    flash("Cantidad de Consumo o Costo Adicional tienen formato numérico inválido.", "danger")
                    has_option_errors = True
                
                if id_producto_interno_form: # Validar si el producto existe, si se proporcionó un ID.
                    producto_vinculado = db.query(Producto).get(id_producto_interno_form)
                    if not producto_vinculado:
                        flash(f"El producto interno con ID {id_producto_interno_form} no existe. La opción se creará sin vínculo.", "warning")
                        id_producto_interno_form = None 

                if not has_option_errors:
                    # Validar unicidad del nombre de la opción DENTRO del grupo.
                    opcion_existente_por_nombre = db.query(OpcionComponenteServicio).filter_by(
                        id_grupo_config=id_grupo_config,
                        nombre_display_cliente=nombre_display_cliente
                    ).first()
                    if opcion_existente_por_nombre:
                        flash(f"Ya existe una opción llamada '{nombre_display_cliente}' en este grupo.", "warning")
                    else:
                        nueva_opcion = OpcionComponenteServicio(
                            id_grupo_config=id_grupo_config,
                            id_producto_interno=id_producto_interno_form,
                            nombre_display_cliente=nombre_display_cliente,
                            descripcion_display_cliente=descripcion_display_cliente,
                            cantidad_consumo_base=cantidad_consumo_base_dec,
                            unidad_consumo_base=unidad_consumo_base,
                            costo_adicional_opcion=costo_adicional_opcion_dec,
                            activo=opcion_activa
                        )
                        db.add(nueva_opcion)
                        db.commit()
                        flash(f"Opción '{nombre_display_cliente}' añadida al grupo '{grupo_config.nombre_grupo}'.", "success")
                        # Redirigir para limpiar el formulario y mostrar la nueva opción en la lista.
                        return redirect(url_for('admin_servicios_bp.admin_vista_gestionar_opciones_componente', id_variante_config=id_variante_config, id_grupo_config=id_grupo_config))
            
            elif accion == 'eliminar_opcion':
                # Lógica para eliminar una opción.
                id_opcion_a_eliminar = request.form.get('id_opcion_componente', type=int)
                if id_opcion_a_eliminar:
                    opcion_a_eliminar = db.query(OpcionComponenteServicio).filter_by(
                        id_opcion_componente=id_opcion_a_eliminar,
                        id_grupo_config=id_grupo_config # Asegurar que pertenece al grupo actual.
                    ).first()
                    if opcion_a_eliminar:
                        # Antes de eliminar, verificar si está siendo usada en alguna cotización.
                        # Esta es una verificación simple, podrías querer una lógica más robusta.
                        usada_en_cotizacion = db.query(DetalleComponenteSeleccionado)\
                                              .filter_by(id_opcion_componente=opcion_a_eliminar.id_opcion_componente)\
                                              .first()
                        if usada_en_cotizacion:
                            flash(f"La opción '{opcion_a_eliminar.nombre_display_cliente}' está siendo utilizada en al menos una cotización (ej. ID Detalle: {usada_en_cotizacion.id_detalle_seleccion}) y no puede ser eliminada. Puedes desactivarla.", "danger")
                        else:
                            db.delete(opcion_a_eliminar)
                            db.commit()
                            flash(f"Opción '{opcion_a_eliminar.nombre_display_cliente}' eliminada.", "success")
                    else:
                        flash("Opción a eliminar no encontrada o no pertenece a este grupo.", "warning")
                else:
                    flash("No se especificó ID de opción para eliminar.", "warning")
                # Redirigir siempre para actualizar la lista.
                return redirect(url_for('admin_servicios_bp.admin_vista_gestionar_opciones_componente', id_variante_config=id_variante_config, id_grupo_config=id_grupo_config))
        
        # Para el método GET o si el POST tuvo errores y se necesita repopular la lista.
        opciones_existentes = db.query(OpcionComponenteServicio).filter_by(id_grupo_config=id_grupo_config).order_by(OpcionComponenteServicio.nombre_display_cliente).all()
        
        return render_template('gestionar_opciones_componente.html',
                               grupo_config=grupo_config,
                               variante_config=grupo_config.variante_servicio_config_ref,
                               opciones_existentes=opciones_existentes,
                               titulo_pagina=f"Gestionar Opciones para: {grupo_config.nombre_grupo}")

    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error al cargar la gestión de opciones: {str(e)}", "danger")
        if id_variante_config:
             return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_variante_config))
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
    finally:
        if db.is_active: db.close()

# --- RUTAS API para Selects Dependientes y Búsquedas ---
@admin_servicios_bp.route('/api/tipos-servicio-base-activos', methods=['GET'])
def api_get_tipos_servicio_base_activos():
    # API para obtener Tipos de Servicio Base activos (usado en el formulario de cotización).
    db = SessionLocal()
    try:
        tipos = db.query(TipoServicioBase.id_tipo_servicio_base, TipoServicioBase.nombre)\
                  .filter(TipoServicioBase.activo == True)\
                  .order_by(TipoServicioBase.nombre)\
                  .all()
        resultado = [{"id": t.id_tipo_servicio_base, "nombre": t.nombre} for t in tipos]
        return jsonify(resultado)
    except Exception as e:
        print(f"Error en api_get_tipos_servicio_base_activos: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if db.is_active:
            db.close()

@admin_servicios_bp.route('/api/variantes-config/niveles-paquete', methods=['GET'])
def api_get_niveles_paquete():
    # API para obtener los niveles de paquete únicos para un Tipo de Servicio Base.
    id_tipo_base_str = request.args.get('id_tipo_base')
    if not id_tipo_base_str or not id_tipo_base_str.isdigit():
        return jsonify({"error": "ID de Tipo de Servicio Base inválido o faltante."}), 400
    
    id_tipo_base = int(id_tipo_base_str)
    db = SessionLocal()
    try:
        paquetes_query = db.query(distinct(VarianteServicioConfig.nivel_paquete))\
                           .filter(VarianteServicioConfig.id_tipo_servicio_base == id_tipo_base)\
                           .filter(VarianteServicioConfig.activo == True)\
                           .filter(VarianteServicioConfig.nivel_paquete != None)\
                           .order_by(VarianteServicioConfig.nivel_paquete)\
                           .all()
        paquetes = [p[0] for p in paquetes_query if p[0]] 
        return jsonify(paquetes)
    except Exception as e:
        print(f"Error en api_get_niveles_paquete: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if db.is_active:
            db.close()

@admin_servicios_bp.route('/api/variantes-config/niveles-perfil', methods=['GET'])
def api_get_niveles_perfil():
    # API para obtener los niveles de perfil únicos para un Tipo de Servicio Base y un Paquete.
    id_tipo_base_str = request.args.get('id_tipo_base')
    paquete_nombre = request.args.get('paquete')

    if not id_tipo_base_str or not id_tipo_base_str.isdigit():
        return jsonify({"error": "ID de Tipo de Servicio Base inválido o faltante."}), 400
    if not paquete_nombre:
        return jsonify({"error": "Nombre del paquete faltante."}), 400
        
    id_tipo_base = int(id_tipo_base_str)
    db = SessionLocal()
    try:
        perfiles_query = db.query(distinct(VarianteServicioConfig.nivel_perfil))\
                           .filter(VarianteServicioConfig.id_tipo_servicio_base == id_tipo_base)\
                           .filter(VarianteServicioConfig.nivel_paquete == paquete_nombre)\
                           .filter(VarianteServicioConfig.activo == True)\
                           .filter(VarianteServicioConfig.nivel_perfil != None)\
                           .order_by(VarianteServicioConfig.nivel_perfil)\
                           .all()
        perfiles = [p[0] for p in perfiles_query if p[0]]
        return jsonify(perfiles)
    except Exception as e:
        print(f"Error en api_get_niveles_perfil: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if db.is_active:
            db.close()

@admin_servicios_bp.route('/api/variante-config/buscar-por-niveles', methods=['GET'])
def api_buscar_variante_por_niveles():
    # API para buscar una Variante de Servicio Config específica por sus niveles.
    id_tipo_base_str = request.args.get('id_tipo_base')
    paquete_nombre = request.args.get('paquete')
    perfil_nombre = request.args.get('perfil')

    if not all([id_tipo_base_str, paquete_nombre, perfil_nombre]):
        return jsonify({"error": "Faltan parámetros: id_tipo_base, paquete o perfil."}), 400
    if not id_tipo_base_str.isdigit():
        return jsonify({"error": "ID de Tipo de Servicio Base debe ser numérico."}), 400

    id_tipo_base = int(id_tipo_base_str)
    db = SessionLocal()
    try:
        variante = db.query(VarianteServicioConfig.id_variante_config, VarianteServicioConfig.nombre_variante)\
                     .filter(VarianteServicioConfig.id_tipo_servicio_base == id_tipo_base)\
                     .filter(VarianteServicioConfig.nivel_paquete == paquete_nombre)\
                     .filter(VarianteServicioConfig.nivel_perfil == perfil_nombre)\
                     .filter(VarianteServicioConfig.activo == True)\
                     .first()
        if variante:
            return jsonify({
                "id_variante_config": variante.id_variante_config,
                "nombre_variante": variante.nombre_variante
            })
        else:
            return jsonify({"error": "No se encontró una variante activa para la combinación especificada."}), 404
    except Exception as e:
        print(f"Error en api_buscar_variante_por_niveles: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if db.is_active:
            db.close()

@admin_servicios_bp.route('/api/variante-config/estructura', methods=['GET'])
def api_get_estructura_variante():
    # API para obtener la estructura completa (grupos y opciones) de una Variante de Servicio.
    id_variante_config_str = request.args.get('id_variante_config')
    if not id_variante_config_str or not id_variante_config_str.isdigit():
        return jsonify({"error": "ID de Variante de Configuración inválido o faltante."}), 400
    
    id_variante_config = int(id_variante_config_str)
    db = SessionLocal()
    try:
        variante = db.query(VarianteServicioConfig).options(
            selectinload(VarianteServicioConfig.grupos_componentes).selectinload(GrupoComponenteConfig.opciones_componente_disponibles).selectinload(OpcionComponenteServicio.producto_interno_ref)
        ).get(id_variante_config)

        if not variante:
            return jsonify({"error": "Variante de servicio no encontrada."}), 404

        resultado = {
            "id_variante_config": variante.id_variante_config,
            "nombre_variante": variante.nombre_variante,
            "grupos": []
        }
        for grupo in sorted(variante.grupos_componentes, key=lambda g: g.orden_display or 0):
            grupo_dict = {
                "id_grupo_config": grupo.id_grupo_config,
                "nombre_grupo": grupo.nombre_grupo,
                "opciones_permitidas_seleccionables": grupo.cantidad_opciones_seleccionables,
                "opciones_disponibles": []
            }
            for opcion in sorted(grupo.opciones_componente_disponibles, key=lambda o: o.nombre_display_cliente):
                if opcion.activo: 
                    producto_info = {}
                    if opcion.producto_interno_ref:
                        producto_info = {
                            "id_producto_interno": opcion.producto_interno_ref.id_producto,
                            "sku": opcion.producto_interno_ref.sku,
                            "nombre_producto": opcion.producto_interno_ref.nombre_producto,
                            "unidad_medida_base": opcion.producto_interno_ref.unidad_medida_base,
                            "es_indivisible": opcion.producto_interno_ref.es_indivisible 
                        }
                    
                    opcion_dict = {
                        "id_opcion_componente": opcion.id_opcion_componente,
                        "nombre_display_cliente": opcion.nombre_display_cliente,
                        "descripcion_display_cliente": opcion.descripcion_display_cliente,
                        "cantidad_consumo_base": float(opcion.cantidad_consumo_base) if opcion.cantidad_consumo_base is not None else 0,
                        "unidad_consumo_base": opcion.unidad_consumo_base,
                        "costo_adicional_opcion": float(opcion.costo_adicional_opcion) if opcion.costo_adicional_opcion is not None else 0,
                        "producto_info": producto_info if producto_info else None 
                    }
                    grupo_dict["opciones_disponibles"].append(opcion_dict)
            resultado["grupos"].append(grupo_dict)
        
        return jsonify(resultado)
    except Exception as e:
        print(f"Error en api_get_estructura_variante: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if db.is_active:
            db.close()
