# /mod_admin_servicios/routes.py
from flask import render_template, request, redirect, url_for, flash, session
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, distinct, exc as sqlalchemy_exc
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
        if db.is_active: db.close()


@admin_servicios_bp.route('/tipos-base/nuevo', methods=['GET', 'POST'])
@admin_servicios_bp.route('/tipos-base/<int:id_tipo_base>/editar', methods=['GET', 'POST'])
def admin_vista_crear_editar_tipo_servicio_base(id_tipo_base=None):
    db = SessionLocal()
    tipo_servicio_existente = None
    if id_tipo_base:
        tipo_servicio_existente = db.query(TipoServicioBase).get(id_tipo_base)
        if not tipo_servicio_existente:
            flash("Tipo de Servicio Base no encontrado.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        descripcion = request.form.get('descripcion', '').strip()
        activo = 'activo' in request.form

        if not nombre:
            flash("El nombre del tipo de servicio es obligatorio.", "danger")
        else:
            try:
                if tipo_servicio_existente: # Editando
                    tipo_servicio_existente.nombre = nombre
                    tipo_servicio_existente.descripcion = descripcion
                    tipo_servicio_existente.activo = activo
                    flash("Tipo de Servicio Base actualizado correctamente.", "success")
                else: # Creando
                    nuevo_tipo = TipoServicioBase(nombre=nombre, descripcion=descripcion, activo=activo)
                    db.add(nuevo_tipo)
                    flash("Tipo de Servicio Base creado correctamente.", "success")
                db.commit()
                return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))
            except sqlalchemy_exc.IntegrityError:
                db.rollback()
                flash("Error: Ya existe un tipo de servicio con ese nombre.", "danger")
            except Exception as e:
                db.rollback()
                flash(f"Error al guardar el tipo de servicio: {str(e)}", "danger")
    
    form_data = request.form if request.method == 'POST' else {} # Para repopular en caso de error
    if request.method == 'GET' and tipo_servicio_existente:
        form_data = { # Poblar con datos existentes al editar (GET)
            'nombre': tipo_servicio_existente.nombre,
            'descripcion': tipo_servicio_existente.descripcion,
            'activo': tipo_servicio_existente.activo
        }


    titulo = "Editar Tipo de Servicio: " + tipo_servicio_existente.nombre if tipo_servicio_existente else "Nuevo Tipo de Servicio Base"
    if db.is_active: db.close()
    return render_template('crear_editar_tipo_servicio_base.html',
                           tipo_servicio=tipo_servicio_existente,
                           form_data_tsb=form_data, # Usar un nombre diferente para los datos del form
                           titulo_pagina=titulo)


@admin_servicios_bp.route('/variantes/todas', methods=['GET'])
def admin_vista_listar_todas_variantes():
    db = SessionLocal()
    try:
        variantes = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref)
        ).order_by(VarianteServicioConfig.id_tipo_servicio_base, VarianteServicioConfig.nombre_variante).all()
        return render_template('listar_variantes_servicio_config.html',
                               variantes_servicio_config=variantes,
                               tipo_servicio_base_asociado=None, # No estamos filtrando por tipo base aquí
                               titulo_pagina="Todas las Variantes de Servicio")
    except Exception as e:
        flash(f"Error al cargar todas las variantes: {str(e)}", "danger")
        return render_template('listar_variantes_servicio_config.html', variantes_servicio_config=[], titulo_pagina="Todas las Variantes de Servicio")
    finally:
        if db.is_active: db.close()


@admin_servicios_bp.route('/tipo-base/<int:id_tipo_servicio_base>/variantes', methods=['GET'])
def admin_vista_listar_variantes_por_tipo(id_tipo_servicio_base):
    db = SessionLocal()
    try:
        tipo_servicio_base = db.query(TipoServicioBase).get(id_tipo_servicio_base)
        if not tipo_servicio_base:
            flash("Tipo de Servicio Base no encontrado.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))

        variantes = db.query(VarianteServicioConfig)\
            .filter_by(id_tipo_servicio_base=id_tipo_servicio_base)\
            .order_by(VarianteServicioConfig.nombre_variante).all()
        
        return render_template('listar_variantes_servicio_config.html',
                               variantes_servicio_config=variantes,
                               tipo_servicio_base_asociado=tipo_servicio_base,
                               titulo_pagina=f"Variantes para: {tipo_servicio_base.nombre}")
    except Exception as e:
        flash(f"Error al cargar variantes para el tipo de servicio: {str(e)}", "danger")
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_tipos_servicio_base'))
    finally:
        if db.is_active: db.close()


@admin_servicios_bp.route('/variante/nueva', methods=['GET', 'POST'])
@admin_servicios_bp.route('/variante/<int:id_variante_config>/editar', methods=['GET', 'POST'])
def admin_vista_crear_editar_variante_config(id_variante_config=None):
    db = SessionLocal()
    variante_existente = None
    es_nuevo_registro = True
    id_tipo_base_preseleccionado = request.args.get('id_tipo_servicio_base', type=int)


    if id_variante_config:
        variante_existente = db.query(VarianteServicioConfig).options(
            selectinload(VarianteServicioConfig.grupos_componentes) # Cargar grupos
        ).get(id_variante_config)
        if not variante_existente:
            flash("Variante de Servicio no encontrada.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
        es_nuevo_registro = False
        id_tipo_base_preseleccionado = variante_existente.id_tipo_servicio_base # Sobrescribir si estamos editando

    if request.method == 'POST':
        id_tipo_base_form = request.form.get('id_tipo_servicio_base', type=int)
        nivel_paquete = request.form.get('nivel_paquete', '').strip()
        nivel_perfil = request.form.get('nivel_perfil', '').strip()
        descripcion_publica = request.form.get('descripcion_publica', '').strip()
        precio_base_sugerido_str = request.form.get('precio_base_sugerido')
        activo = 'activo' in request.form
        
        nombre_variante_manual = request.form.get('nombre_variante', '').strip()


        if not id_tipo_base_form or not nivel_paquete or not nivel_perfil:
            flash("Tipo de Servicio Base, Nivel de Paquete y Nivel de Perfil son obligatorios.", "danger")
        else:
            tipo_base_obj = db.query(TipoServicioBase).get(id_tipo_base_form)
            if not tipo_base_obj:
                flash("Tipo de Servicio Base seleccionado no es válido.", "danger")
            else:
                nombre_variante_generado = f"{tipo_base_obj.nombre} - {nivel_paquete} - {nivel_perfil}"
                nombre_final_variante = nombre_variante_manual if nombre_variante_manual else nombre_variante_generado

                try:
                    precio_base_sugerido = Decimal(precio_base_sugerido_str) if precio_base_sugerido_str else None

                    if variante_existente: # Editando
                        variante_existente.id_tipo_servicio_base = id_tipo_base_form # No debería cambiar si está deshabilitado
                        variante_existente.nivel_paquete = nivel_paquete
                        variante_existente.nivel_perfil = nivel_perfil
                        variante_existente.nombre_variante = nombre_final_variante
                        variante_existente.descripcion_publica = descripcion_publica
                        variante_existente.precio_base_sugerido = precio_base_sugerido
                        variante_existente.activo = activo
                        flash("Variante de Servicio actualizada correctamente.", "success")
                    else: # Creando
                        nueva_variante = VarianteServicioConfig(
                            id_tipo_servicio_base=id_tipo_base_form,
                            nivel_paquete=nivel_paquete,
                            nivel_perfil=nivel_perfil,
                            nombre_variante=nombre_final_variante,
                            descripcion_publica=descripcion_publica,
                            precio_base_sugerido=precio_base_sugerido,
                            activo=activo
                        )
                        db.add(nueva_variante)
                        db.flush() # Para obtener el ID de la nueva variante
                        variante_existente = nueva_variante # Para la redirección
                        flash("Variante de Servicio creada correctamente. Ahora puedes añadir grupos de componentes.", "success")
                    
                    db.commit()
                    # Redirigir a la misma página de edición para que se muestre la sección de grupos
                    return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=variante_existente.id_variante_config))

                except InvalidOperation:
                    db.rollback()
                    flash("Error: El precio base sugerido debe ser un número válido.", "danger")
                except sqlalchemy_exc.IntegrityError:
                    db.rollback()
                    flash("Error: Podría haber un conflicto con otra variante (ej. nombre duplicado si tienes una restricción única).", "danger")
                except Exception as e:
                    db.rollback()
                    flash(f"Error al guardar la variante: {str(e)}", "danger")
    
    form_data_para_plantilla = {}
    if request.method == 'POST': # Si hubo error y se repopula
        form_data_para_plantilla = request.form.to_dict()
    elif variante_existente: # Si es GET y estamos editando
        form_data_para_plantilla = {
            'id_tipo_servicio_base': variante_existente.id_tipo_servicio_base,
            'nivel_paquete': variante_existente.nivel_paquete,
            'nivel_perfil': variante_existente.nivel_perfil,
            'nombre_variante': variante_existente.nombre_variante,
            'descripcion_publica': variante_existente.descripcion_publica,
            'precio_base_sugerido': '{:.2f}'.format(variante_existente.precio_base_sugerido) if variante_existente.precio_base_sugerido is not None else '',
            'activo': variante_existente.activo
        }
    elif id_tipo_base_preseleccionado: # Si es GET para nuevo, con tipo base preseleccionado
         form_data_para_plantilla['id_tipo_servicio_base'] = id_tipo_base_preseleccionado


    todos_tipos_base = db.query(TipoServicioBase).filter_by(activo=True).order_by(TipoServicioBase.nombre).all()
    
    titulo_pagina_dinamico = "Editar Variante: " + (variante_existente.nombre_variante if variante_existente else "") if variante_existente else "Nueva Variante de Servicio"
    if not variante_existente and id_tipo_base_preseleccionado:
        tipo_base_seleccionado = db.query(TipoServicioBase).get(id_tipo_base_preseleccionado)
        if tipo_base_seleccionado:
            titulo_pagina_dinamico = f"Nueva Variante para: {tipo_base_seleccionado.nombre}"


    if db.is_active: db.close()
    return render_template('crear_editar_variante_servicio_config.html',
                           variante_config_obj=variante_existente,
                           todos_tipos_servicio_base=todos_tipos_base,
                           variante_config_form_data=form_data_para_plantilla,
                           es_nuevo=es_nuevo_registro,
                           id_tipo_servicio_base_preseleccionado=id_tipo_base_preseleccionado,
                           titulo_pagina=titulo_pagina_dinamico)


@admin_servicios_bp.route('/variante/<int:id_variante_config>/grupo/nuevo', methods=['GET', 'POST'])
@admin_servicios_bp.route('/variante/<int:id_variante_config>/grupo/<int:id_grupo_config>/editar', methods=['GET', 'POST'])
def admin_vista_crear_editar_grupo_componente(id_variante_config, id_grupo_config=None):
    db = SessionLocal()
    variante_padre = db.query(VarianteServicioConfig).get(id_variante_config)
    if not variante_padre:
        flash("Variante de Servicio no encontrada.", "danger")
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))

    grupo_existente = None
    es_nuevo_grupo = True
    if id_grupo_config:
        grupo_existente = db.query(GrupoComponenteConfig).filter_by(id_grupo_config=id_grupo_config, id_variante_config=id_variante_config).first()
        if not grupo_existente:
            flash("Grupo de Componentes no encontrado para esta variante.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_variante_config))
        es_nuevo_grupo = False

    if request.method == 'POST':
        nombre_grupo = request.form.get('nombre_grupo', '').strip()
        cantidad_opciones_str = request.form.get('cantidad_opciones_seleccionables', '1')
        # porcentaje_total_str = request.form.get('porcentaje_del_total_servicio') # Campo eliminado temporalmente

        if not nombre_grupo:
            flash("El nombre del grupo es obligatorio.", "danger")
        else:
            try:
                cantidad_opciones = int(cantidad_opciones_str)
                # porcentaje_total = Decimal(porcentaje_total_str) / Decimal(100) if porcentaje_total_str else None

                if grupo_existente: # Editando
                    grupo_existente.nombre_grupo = nombre_grupo
                    grupo_existente.cantidad_opciones_seleccionables = cantidad_opciones
                    # grupo_existente.porcentaje_del_total_servicio = porcentaje_total
                    flash("Grupo de Componentes actualizado.", "success")
                else: # Creando
                    nuevo_grupo = GrupoComponenteConfig(
                        id_variante_config=id_variante_config,
                        nombre_grupo=nombre_grupo,
                        cantidad_opciones_seleccionables=cantidad_opciones
                        # porcentaje_del_total_servicio=porcentaje_total
                    )
                    db.add(nuevo_grupo)
                    flash("Grupo de Componentes creado.", "success")
                db.commit()
                return redirect(url_for('admin_servicios_bp.admin_vista_crear_editar_variante_config', id_variante_config=id_variante_config))
            except ValueError:
                db.rollback()
                flash("Error: La cantidad de opciones debe ser un número entero.", "danger")
            except InvalidOperation: # Para Decimal
                db.rollback()
                flash("Error: El porcentaje debe ser un número válido.", "danger")
            except Exception as e:
                db.rollback()
                flash(f"Error al guardar el grupo: {str(e)}", "danger")
    
    form_values_grupo = {}
    if request.method == 'POST':
        form_values_grupo = request.form.to_dict()
    elif grupo_existente:
        form_values_grupo = {
            'nombre_grupo': grupo_existente.nombre_grupo,
            'cantidad_opciones_seleccionables': str(grupo_existente.cantidad_opciones_seleccionables),
            # 'porcentaje_del_total_servicio': str(grupo_existente.porcentaje_del_total_servicio * 100) if grupo_existente.porcentaje_del_total_servicio is not None else ''
        }


    titulo_pagina_grupo = "Editar Grupo: " + (grupo_existente.nombre_grupo if grupo_existente else "") if grupo_existente else f"Nuevo Grupo para: {variante_padre.nombre_variante}"
    if db.is_active: db.close()
    return render_template('crear_editar_grupo_componente.html',
                           variante_config=variante_padre,
                           grupo_config_original=grupo_existente,
                           form_values=form_values_grupo,
                           es_nuevo=es_nuevo_grupo,
                           titulo_pagina=titulo_pagina_grupo)

# Rutas para gestionar opciones dentro de un grupo
@admin_servicios_bp.route('/variante/<int:id_variante_config>/grupo/<int:id_grupo_config>/opciones', methods=['GET', 'POST'])
def admin_vista_gestionar_opciones_componente(id_variante_config, id_grupo_config):
    db = SessionLocal()
    # Obtener el parámetro 'origin' de la URL
    origin_page = request.args.get('origin')

    variante_config = db.query(VarianteServicioConfig).options(
        joinedload(VarianteServicioConfig.tipo_servicio_base_ref)
    ).get(id_variante_config)
    grupo_config = db.query(GrupoComponenteConfig).filter_by(id_grupo_config=id_grupo_config, id_variante_config=id_variante_config).first()

    if not variante_config or not grupo_config:
        flash("Variante o Grupo no encontrado.", "danger")
        return redirect(url_for('admin_servicios_bp.admin_dashboard_servicios'))

    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'crear_opcion':
            nombre_display = request.form.get('nombre_display_cliente_opcion', '').strip()
            cantidad_consumo_str = request.form.get('cantidad_consumo_base_opcion', '1')
            unidad_consumo = request.form.get('unidad_consumo_base_opcion', '').strip()
            id_producto_interno_str = request.form.get('id_producto_interno_opcion')
            costo_adicional_str = request.form.get('costo_adicional_opcion_val', '0.00')
            activo_opcion = 'activo_opcion' in request.form

            if not nombre_display or not cantidad_consumo_str or not unidad_consumo:
                flash("Nombre, Cantidad Base y Unidad son obligatorios para la nueva opción.", "danger")
            else:
                try:
                    cantidad_consumo = Decimal(cantidad_consumo_str)
                    id_producto_interno = int(id_producto_interno_str) if id_producto_interno_str and id_producto_interno_str.isdigit() else None
                    costo_adicional = Decimal(costo_adicional_str) if costo_adicional_str else Decimal('0.00')

                    if id_producto_interno and not db.query(Producto).get(id_producto_interno):
                        flash("El producto interno seleccionado para vincular no existe.", "warning")
                    else:
                        nueva_opcion = OpcionComponenteServicio(
                            id_grupo_config=id_grupo_config,
                            nombre_display_cliente=nombre_display,
                            cantidad_consumo_base=cantidad_consumo,
                            unidad_consumo_base=unidad_consumo,
                            id_producto_interno=id_producto_interno,
                            costo_adicional_opcion=costo_adicional,
                            activo=activo_opcion
                        )
                        db.add(nueva_opcion)
                        db.commit()
                        flash("Nueva opción de componente añadida correctamente.", "success")
                        # Redirigir a la misma página para evitar reenvío de formulario
                        return redirect(url_for('admin_servicios_bp.admin_vista_gestionar_opciones_componente', id_variante_config=id_variante_config, id_grupo_config=id_grupo_config, origin=origin_page))
                except ValueError: # Para int()
                    db.rollback()
                    flash("Error: Cantidad base debe ser un número. ID de producto debe ser un entero si se provee.", "danger")
                except InvalidOperation: # Para Decimal()
                    db.rollback()
                    flash("Error: Cantidad base o costo adicional deben ser números válidos.", "danger")
                except Exception as e:
                    db.rollback()
                    flash(f"Error al crear la opción: {str(e)}", "danger")
        
        elif accion == 'actualizar_opcion':
            id_opcion_a_actualizar = request.form.get('id_opcion_componente_edit')
            opcion_a_editar = db.query(OpcionComponenteServicio).get(id_opcion_a_actualizar)
            if opcion_a_editar and opcion_a_editar.id_grupo_config == id_grupo_config:
                opcion_a_editar.nombre_display_cliente = request.form.get(f'nombre_display_cliente_opcion_{id_opcion_a_actualizar}', opcion_a_editar.nombre_display_cliente).strip()
                opcion_a_editar.cantidad_consumo_base = Decimal(request.form.get(f'cantidad_consumo_base_opcion_{id_opcion_a_actualizar}', str(opcion_a_editar.cantidad_consumo_base)))
                opcion_a_editar.unidad_consumo_base = request.form.get(f'unidad_consumo_base_opcion_{id_opcion_a_actualizar}', opcion_a_editar.unidad_consumo_base).strip()
                id_prod_interno_edit_str = request.form.get(f'id_producto_interno_opcion_{id_opcion_a_actualizar}')
                opcion_a_editar.id_producto_interno = int(id_prod_interno_edit_str) if id_prod_interno_edit_str and id_prod_interno_edit_str.isdigit() else None
                costo_adic_edit_str = request.form.get(f'costo_adicional_opcion_val_{id_opcion_a_actualizar}', '0.00')
                opcion_a_editar.costo_adicional_opcion = Decimal(costo_adic_edit_str) if costo_adic_edit_str else Decimal('0.00')
                opcion_a_editar.activo = f'activo_opcion_{id_opcion_a_actualizar}' in request.form
                try:
                    db.commit()
                    flash(f"Opción '{opcion_a_editar.nombre_display_cliente}' actualizada.", "success")
                except Exception as e:
                    db.rollback()
                    flash(f"Error al actualizar la opción: {str(e)}", "danger")
                return redirect(url_for('admin_servicios_bp.admin_vista_gestionar_opciones_componente', id_variante_config=id_variante_config, id_grupo_config=id_grupo_config, origin=origin_page))
            else:
                flash("Opción a editar no encontrada o no pertenece a este grupo.", "warning")


    opciones_del_grupo = db.query(OpcionComponenteServicio).filter_by(id_grupo_config=id_grupo_config)\
        .options(joinedload(OpcionComponenteServicio.producto_interno_ref))\
        .order_by(OpcionComponenteServicio.nombre_display_cliente).all()
    
    if db.is_active: db.close()
    return render_template('gestionar_opciones_componente.html',
                           variante_config=variante_config,
                           grupo_config=grupo_config,
                           opciones_componente=opciones_del_grupo,
                           origin_page=origin_page, # Pasar origin a la plantilla
                           titulo_pagina=f"Opciones para: {grupo_config.nombre_grupo}")


@admin_servicios_bp.route('/variante/<int:id_variante_config>/detalle', methods=['GET'])
def admin_vista_detalle_variante_config(id_variante_config):
    db = SessionLocal()
    try:
        variante = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref),
            selectinload(VarianteServicioConfig.grupos_componentes).selectinload(GrupoComponenteConfig.opciones_componente_disponibles).joinedload(OpcionComponenteServicio.producto_interno_ref)
        ).get(id_variante_config)

        if not variante:
            flash("Variante de servicio no encontrada.", "danger")
            return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
        
        titulo = f"Detalle: {variante.nombre_variante} ({variante.tipo_servicio_base_ref.nombre})"
        return render_template('detalle_variante_servicio_config.html',
                               variante_config=variante,
                               titulo_pagina=titulo)
    except Exception as e:
        flash(f"Error al cargar detalle de la variante: {str(e)}", "danger")
        return redirect(url_for('admin_servicios_bp.admin_vista_listar_todas_variantes'))
    finally:
        if db.is_active: db.close()

@admin_servicios_bp.route('/grupo-componente/<int:id_grupo_config>/eliminar', methods=['DELETE'])
def admin_api_eliminar_grupo_componente(id_grupo_config):
    db = SessionLocal()
    try:
        grupo_a_eliminar = db.query(GrupoComponenteConfig).get(id_grupo_config)
        if not grupo_a_eliminar:
            return jsonify({"success": False, "message": "Grupo no encontrado."}), 404
        
        # Opcional: verificar si hay opciones asociadas y qué hacer (eliminar en cascada o prevenir)
        # SQLAlchemy con cascade="all, delete-orphan" en la relación debería manejarlos.
        
        db.delete(grupo_a_eliminar)
        db.commit()
        return jsonify({"success": True, "message": "Grupo de componentes eliminado correctamente."})
    except Exception as e:
        db.rollback()
        print(f"Error al eliminar grupo de componentes: {str(e)}")
        return jsonify({"success": False, "message": f"Error al eliminar el grupo: {str(e)}"}), 500
    finally:
        if db.is_active: db.close()

@admin_servicios_bp.route('/opcion-componente/<int:id_opcion_componente>/eliminar', methods=['DELETE'])
def admin_api_eliminar_opcion_componente(id_opcion_componente):
    db = SessionLocal()
    try:
        opcion_a_eliminar = db.query(OpcionComponenteServicio).get(id_opcion_componente)
        if not opcion_a_eliminar:
            return jsonify({"success": False, "message": "Opción de componente no encontrada."}), 404
        
        db.delete(opcion_a_eliminar)
        db.commit()
        return jsonify({"success": True, "message": "Opción de componente eliminada correctamente."})
    except Exception as e:
        db.rollback()
        print(f"Error al eliminar opción de componente: {str(e)}")
        return jsonify({"success": False, "message": f"Error al eliminar la opción: {str(e)}"}), 500
    finally:
        if db.is_active: db.close()


# --- RUTAS API para Selects Dinámicos en Cotizaciones ---
@admin_servicios_bp.route('/api/niveles-paquete', methods=['GET'])
def api_get_niveles_paquete():
    id_tipo_base = request.args.get('id_tipo_base', type=int)
    if not id_tipo_base:
        return jsonify([])
    db = SessionLocal()
    try:
        niveles = db.query(VarianteServicioConfig.nivel_paquete)\
            .filter(VarianteServicioConfig.id_tipo_servicio_base == id_tipo_base)\
            .filter(VarianteServicioConfig.activo == True)\
            .distinct()\
            .order_by(VarianteServicioConfig.nivel_paquete)\
            .all()
        return jsonify([nivel[0] for nivel in niveles if nivel[0] is not None])
    except Exception as e:
        print(f"Error en api_get_niveles_paquete: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if db.is_active: db.close()

@admin_servicios_bp.route('/api/niveles-perfil', methods=['GET'])
def api_get_niveles_perfil():
    id_tipo_base = request.args.get('id_tipo_base', type=int)
    paquete = request.args.get('paquete')
    if not id_tipo_base or not paquete:
        return jsonify([])
    db = SessionLocal()
    try:
        niveles = db.query(VarianteServicioConfig.nivel_perfil)\
            .filter(VarianteServicioConfig.id_tipo_servicio_base == id_tipo_base)\
            .filter(VarianteServicioConfig.nivel_paquete == paquete)\
            .filter(VarianteServicioConfig.activo == True)\
            .distinct()\
            .order_by(VarianteServicioConfig.nivel_perfil)\
            .all()
        return jsonify([nivel[0] for nivel in niveles if nivel[0] is not None])
    except Exception as e:
        print(f"Error en api_get_niveles_perfil: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if db.is_active: db.close()

@admin_servicios_bp.route('/api/buscar-variante', methods=['GET'])
def api_buscar_variante_por_niveles():
    id_tipo_base = request.args.get('id_tipo_base', type=int)
    paquete = request.args.get('paquete')
    perfil = request.args.get('perfil')

    if not all([id_tipo_base, paquete, perfil]):
        return jsonify({"error": "Faltan parámetros: id_tipo_base, paquete o perfil"}), 400
    
    db = SessionLocal()
    try:
        variante = db.query(VarianteServicioConfig)\
            .filter_by(id_tipo_servicio_base=id_tipo_base, nivel_paquete=paquete, nivel_perfil=perfil, activo=True)\
            .first()
        
        if variante:
            return jsonify({
                "id_variante_config": variante.id_variante_config,
                "nombre_variante": variante.nombre_variante,
                "descripcion_publica": variante.descripcion_publica,
                "precio_base_sugerido": float(variante.precio_base_sugerido) if variante.precio_base_sugerido is not None else None
            })
        else:
            return jsonify({"error": "Variante no encontrada"}), 404
    except Exception as e:
        print(f"Error en api_buscar_variante_por_niveles: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if db.is_active: db.close()


@admin_servicios_bp.route('/api/variante-estructura', methods=['GET'])
def api_get_estructura_variante():
    id_variante = request.args.get('id_variante_config', type=int)
    if not id_variante:
        return jsonify({"error": "ID de variante no proporcionado"}), 400
    
    db = SessionLocal()
    try:
        variante = db.query(VarianteServicioConfig).options(
            selectinload(VarianteServicioConfig.grupos_componentes).selectinload(GrupoComponenteConfig.opciones_componente_disponibles).joinedload(OpcionComponenteServicio.producto_interno_ref)
        ).get(id_variante)

        if not variante:
            return jsonify({"error": "Variante no encontrada"}), 404

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
                if opcion.activo: # Solo incluir opciones activas
                    producto_info = None
                    if opcion.producto_interno_ref:
                        producto_info = {
                            "id_producto_interno": opcion.id_producto_interno,
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
