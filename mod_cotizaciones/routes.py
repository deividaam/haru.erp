# /mod_cotizaciones/routes.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, distinct
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, ROUND_DOWN, InvalidOperation
from datetime import date, datetime # Asegurar datetime
from math import ceil

from . import cotizaciones_bp
from database import SessionLocal
from models import (
    Proyecto, Cotizacion, ItemCotizacion, DetalleComponenteSeleccionado,
    VarianteServicioConfig, OpcionComponenteServicio, TipoServicioBase, Producto
)

# --- RUTAS PARA GESTIÓN DE COTIZACIONES ---

@cotizaciones_bp.route('/', methods=['GET'])
def vista_listar_cotizaciones():
    db = SessionLocal()
    try:
        cotizaciones = db.query(Cotizacion).options(
            joinedload(Cotizacion.proyecto)
        ).order_by(desc(Cotizacion.fecha_emision), desc(Cotizacion.id_cotizacion)).all()
        return render_template('listar_cotizaciones.html',
                               cotizaciones=cotizaciones,
                               proyecto_asociado=None,
                               titulo_pagina="Listado de Cotizaciones")
    except Exception as e:
        flash(f"Error al cargar el listado de cotizaciones: {str(e)}", "danger")
        return render_template('listar_cotizaciones.html', cotizaciones=[], proyecto_asociado=None, titulo_pagina="Listado de Cotizaciones")
    finally:
        if db.is_active:
            db.close()

@cotizaciones_bp.route('/por-proyecto/<int:id_proyecto>', methods=['GET'])
def vista_listar_cotizaciones_por_proyecto(id_proyecto):
    db = SessionLocal()
    proyecto = None 
    try:
        proyecto = db.query(Proyecto).get(id_proyecto)
        if not proyecto:
            flash("Proyecto no encontrado.", "danger")
            return redirect(url_for('proyectos_bp.vista_listar_proyectos'))

        cotizaciones = db.query(Cotizacion).filter_by(id_proyecto=id_proyecto)\
            .order_by(desc(Cotizacion.version)).all()

        return render_template('listar_cotizaciones.html',
                               cotizaciones=cotizaciones,
                               proyecto_asociado=proyecto,
                               titulo_pagina=f"Cotizaciones para: {proyecto.nombre_evento}")
    except Exception as e:
        flash(f"Error al cargar cotizaciones del proyecto: {str(e)}", "danger")
        redirect_url = url_for('proyectos_bp.vista_listar_proyectos')
        if proyecto: 
            redirect_url = url_for('proyectos_bp.vista_detalle_proyecto', id_proyecto=id_proyecto)
        return redirect(redirect_url)
    finally:
        if db.is_active:
            db.close()

@cotizaciones_bp.route('/nueva/seleccionar-proyecto', methods=['GET', 'POST'])
def vista_crear_cotizacion_paso1_proyecto():
    if request.method == 'POST':
        id_proyecto_seleccionado = request.form.get('id_proyecto_seleccionado')
        if not id_proyecto_seleccionado or not id_proyecto_seleccionado.isdigit():
            flash("Debes seleccionar un proyecto válido.", "warning")
            return redirect(url_for('cotizaciones_bp.vista_crear_cotizacion_paso1_proyecto'))
        return redirect(url_for('cotizaciones_bp.vista_crear_cotizacion_paso2_configurar', id_proyecto=int(id_proyecto_seleccionado)))

    db = SessionLocal()
    try:
        proyectos = db.query(Proyecto).order_by(Proyecto.nombre_evento).all()
        return render_template('crear_cotizacion_paso1_proyecto.html',
                               proyectos_existentes=proyectos,
                               titulo_pagina="Nueva Cotización: Seleccionar Proyecto")
    except Exception as e:
        flash(f"Error al cargar proyectos para seleccionar: {str(e)}", "danger")
        return render_template('crear_cotizacion_paso1_proyecto.html', proyectos_existentes=[], titulo_pagina="Nueva Cotización: Seleccionar Proyecto")
    finally:
        if db.is_active:
            db.close()

@cotizaciones_bp.route('/nueva/configurar/proyecto/<int:id_proyecto>', methods=['GET'])
@cotizaciones_bp.route('/<int:id_cotizacion>/editar', methods=['GET'])
def vista_crear_cotizacion_paso2_configurar(id_proyecto=None, id_cotizacion=None):
    db = SessionLocal()
    proyecto = None 
    try:
        cotizacion_obj_para_template = None
        es_nueva_cotizacion = True
        fecha_hoy_iso = date.today().isoformat()
        
        tipos_servicio_base_activos = db.query(TipoServicioBase)\
                                        .filter(TipoServicioBase.activo == True)\
                                        .order_by(TipoServicioBase.nombre)\
                                        .all()

        if id_cotizacion: 
            cotizacion_obj_para_template = db.query(Cotizacion).options(
                joinedload(Cotizacion.proyecto),
                selectinload(Cotizacion.items_cotizacion).options(
                    selectinload(ItemCotizacion.variante_servicio_config_usada),
                    selectinload(ItemCotizacion.componentes_seleccionados).options(
                        selectinload(DetalleComponenteSeleccionado.opcion_componente_elegida).options(
                            selectinload(OpcionComponenteServicio.producto_interno_ref)
                        )
                    )
                )
            ).get(id_cotizacion)

            if not cotizacion_obj_para_template:
                flash("Cotización no encontrada.", "danger")
                return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones'))
            proyecto = cotizacion_obj_para_template.proyecto
            es_nueva_cotizacion = False
            titulo = f"Editar Cotización V{cotizacion_obj_para_template.version} para: {proyecto.nombre_evento}"
        
        elif id_proyecto: 
            proyecto = db.query(Proyecto).get(id_proyecto)
            if not proyecto:
                flash("Proyecto no encontrado para crear la cotización.", "danger")
                return redirect(url_for('cotizaciones_bp.vista_crear_cotizacion_paso1_proyecto'))
            
            ultima_cot_proyecto = db.query(Cotizacion.version).filter_by(id_proyecto=id_proyecto).order_by(desc(Cotizacion.version)).first()
            nueva_version = (ultima_cot_proyecto[0] + 1) if ultima_cot_proyecto else 1
            
            cotizacion_obj_para_template = Cotizacion(
                id_proyecto=id_proyecto, 
                version=nueva_version,
                fecha_emision=date.today(),
                estado="Borrador",
                # Establecer porcentajes por defecto para nuevas cotizaciones
                porcentaje_descuento_global=Decimal('0.00'),
                porcentaje_impuestos=Decimal('16.00') # IVA por defecto en México
            )
            if proyecto: 
                cotizacion_obj_para_template.monto_costos_logisticos = (proyecto.costo_transporte_estimado or Decimal('0.0')) + \
                                                                      (proyecto.costo_viaticos_estimado or Decimal('0.0')) + \
                                                                      (proyecto.costo_hospedaje_estimado or Decimal('0.0'))
            titulo = f"Nueva Cotización (V{nueva_version}) para: {proyecto.nombre_evento}"
        
        else: 
            flash("Se requiere un proyecto o una cotización existente.", "danger")
            return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones'))

        todas_variantes_config_obj_list = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref) 
        ).filter(VarianteServicioConfig.activo==True).order_by(VarianteServicioConfig.id_tipo_servicio_base, VarianteServicioConfig.nombre_variante).all()
        
        todas_variantes_config_serializable = []
        for variante in todas_variantes_config_obj_list:
            todas_variantes_config_serializable.append({
                "id_variante_config": variante.id_variante_config,
                "nombre_variante": variante.nombre_variante,
                "id_tipo_servicio_base": variante.id_tipo_servicio_base,
                "nombre_tipo_servicio_base": variante.tipo_servicio_base_ref.nombre if variante.tipo_servicio_base_ref else None,
                "nivel_paquete": variante.nivel_paquete,
                "nivel_perfil": variante.nivel_perfil,
                "precio_base_sugerido": float(variante.precio_base_sugerido) if variante.precio_base_sugerido is not None else None
            })

        return render_template('configurar_cotizacion.html',
                               proyecto=proyecto,
                               cotizacion=cotizacion_obj_para_template, 
                               es_nueva_cotizacion=es_nueva_cotizacion,
                               fecha_hoy=fecha_hoy_iso,
                               todos_tipos_servicio_base_activos=tipos_servicio_base_activos,
                               todas_variantes_config=todas_variantes_config_serializable, 
                               titulo_pagina=titulo,
                               enumerate=enumerate) 
    except Exception as e:
        error_type_name = type(e).__name__
        error_message_str = str(e)
        print(f"ERROR in vista_crear_cotizacion_paso2_configurar: {error_type_name} - {error_message_str}")
        import traceback
        traceback.print_exc()
        
        flash("Error al preparar la configuración de la cotización. Por favor, intente de nuevo o contacte a soporte si el problema persiste.", "danger")

        if id_proyecto and not id_cotizacion: 
             return redirect(url_for('proyectos_bp.vista_detalle_proyecto', id_proyecto=id_proyecto))
        return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones')) 
    finally:
        if db.is_active:
            db.close()

@cotizaciones_bp.route('/guardar', methods=['POST'])
def vista_guardar_configuracion_cotizacion():
    db = SessionLocal()
    id_proyecto_form = request.form.get('id_proyecto', type=int)
    id_cotizacion_existente = request.form.get('id_cotizacion', type=int)
    
    proyecto_para_repopular_original = None 
    cotizacion_para_repopular_original = None 
    
    try:
        proyecto_para_repopular_original = db.query(Proyecto).get(id_proyecto_form)
        if not proyecto_para_repopular_original:
            flash("Proyecto asociado no encontrado.", "danger")
            return redirect(url_for('cotizaciones_bp.vista_crear_cotizacion_paso1_proyecto'))

        numero_invitados_cotizacion_str = request.form.get('numero_invitados_cotizacion')
        numero_invitados_cotizacion = int(numero_invitados_cotizacion_str) if numero_invitados_cotizacion_str and numero_invitados_cotizacion_str.isdigit() else None
        
        accion = request.form.get('accion', 'guardar_borrador')
        fecha_emision_form = date.fromisoformat(request.form.get('fecha_emision'))
        fecha_validez_form_str = request.form.get('fecha_validez')
        fecha_validez_form = date.fromisoformat(fecha_validez_form_str) if fecha_validez_form_str else None
        estado_form = request.form.get('estado', 'Borrador')
        monto_costos_logisticos = Decimal(request.form.get('monto_costos_logisticos', '0.00'))
        
        # Leer porcentajes del formulario
        porcentaje_descuento_str = request.form.get('porcentaje_descuento_global', '0.00')
        porcentaje_impuestos_str = request.form.get('porcentaje_impuestos', '16.00') # Default IVA 16%

        try:
            porcentaje_descuento_form = Decimal(porcentaje_descuento_str) if porcentaje_descuento_str else Decimal('0.00')
            porcentaje_impuestos_form = Decimal(porcentaje_impuestos_str) if porcentaje_impuestos_str else Decimal('0.00')
        except InvalidOperation:
            flash("Formato de porcentaje de descuento o impuestos inválido.", "danger")
            # Necesitarás repopular el formulario aquí si este error ocurre
            # (Lógica de repopulación omitida por brevedad, pero es similar al bloque finally)
            return redirect(request.referrer or url_for('cotizaciones_bp.vista_listar_cotizaciones'))


        terminos_condiciones_form = request.form.get('terminos_condiciones')
        notas_cotizacion_form = request.form.get('notas_cotizacion')

        cotizacion_obj = None
        if id_cotizacion_existente:
            cotizacion_obj = db.query(Cotizacion).get(id_cotizacion_existente)
            if not cotizacion_obj:
                flash("Cotización a editar no encontrada.", "danger")
                return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones_por_proyecto', id_proyecto=id_proyecto_form))
            
            cotizacion_obj.fecha_emision = fecha_emision_form
            cotizacion_obj.fecha_validez = fecha_validez_form
            cotizacion_obj.estado = estado_form
            cotizacion_obj.numero_invitados_override = numero_invitados_cotizacion if numero_invitados_cotizacion != proyecto_para_repopular_original.numero_invitados else None
            cotizacion_obj.monto_costos_logisticos = monto_costos_logisticos
            cotizacion_obj.porcentaje_descuento_global = porcentaje_descuento_form
            cotizacion_obj.porcentaje_impuestos = porcentaje_impuestos_form
            cotizacion_obj.terminos_condiciones = terminos_condiciones_form
            cotizacion_obj.notas_cotizacion = notas_cotizacion_form
        
        else: 
            version_form = request.form.get('version', type=int, default=1)
            cotizacion_obj = Cotizacion(
                id_proyecto=id_proyecto_form,
                version=version_form,
                fecha_emision=fecha_emision_form,
                fecha_validez=fecha_validez_form,
                estado=estado_form,
                numero_invitados_override=numero_invitados_cotizacion if numero_invitados_cotizacion != proyecto_para_repopular_original.numero_invitados else None,
                monto_costos_logisticos=monto_costos_logisticos,
                porcentaje_descuento_global=porcentaje_descuento_form,
                porcentaje_impuestos=porcentaje_impuestos_form,
                terminos_condiciones=terminos_condiciones_form,
                notas_cotizacion=notas_cotizacion_form
            )
            db.add(cotizacion_obj)
            db.flush() 

        cotizacion_para_repopular_original = cotizacion_obj 

        if id_cotizacion_existente:
            items_actuales_ids = [item.id_item_cotizacion for item in cotizacion_obj.items_cotizacion]
            if items_actuales_ids:
                db.query(DetalleComponenteSeleccionado).filter(DetalleComponenteSeleccionado.id_item_cotizacion.in_(items_actuales_ids)).delete(synchronize_session=False)
            db.query(ItemCotizacion).filter_by(id_cotizacion=id_cotizacion_existente).delete(synchronize_session=False)
            db.flush() 
            cotizacion_obj.items_cotizacion = [] 

        monto_total_servicios_calculado = Decimal('0.00')
        
        item_idx = 0
        while f'items[{item_idx}][nombre_display_servicio]' in request.form:
            nombre_display_item = request.form.get(f'items[{item_idx}][nombre_display_servicio]')
            id_variante_item_str = request.form.get(f'items[{item_idx}][id_variante_servicio_config]')
            id_variante_item = int(id_variante_item_str) if id_variante_item_str and id_variante_item_str.isdigit() else None
            cantidad_servicio_str = request.form.get(f'items[{item_idx}][cantidad_servicio]', '1.0')
            cantidad_servicio = Decimal(cantidad_servicio_str) if cantidad_servicio_str else Decimal('1.0')
            descripcion_item = request.form.get(f'items[{item_idx}][descripcion_servicio_cotizado]')
            precio_total_item_calculado_form = Decimal(request.form.get(f'items[{item_idx}][precio_total_item_calculado]', '0.00'))
            
            numero_invitados_item_str = request.form.get(f'items[{item_idx}][numero_invitados_servicio_item]')
            numero_invitados_item = int(numero_invitados_item_str) if numero_invitados_item_str and numero_invitados_item_str.isdigit() else None


            nuevo_item_cot = ItemCotizacion(
                id_cotizacion=cotizacion_obj.id_cotizacion, 
                id_variante_servicio_config=id_variante_item,
                nombre_display_servicio=nombre_display_item,
                descripcion_servicio_cotizado=descripcion_item,
                cantidad_servicio=cantidad_servicio,
                precio_total_item_calculado = precio_total_item_calculado_form,
                numero_invitados_servicio_item = numero_invitados_item 
            )
            db.add(nuevo_item_cot)
            db.flush() 

            comp_idx = 0
            while f'items[{item_idx}][componentes][{comp_idx}][id_opcion_componente]' in request.form:
                id_opcion_comp_form_str = request.form[f'items[{item_idx}][componentes][{comp_idx}][id_opcion_componente]']
                if id_opcion_comp_form_str and id_opcion_comp_form_str.isdigit():
                    id_opcion_comp_form = int(id_opcion_comp_form_str)
                    opcion_obj_db = db.query(OpcionComponenteServicio).options(
                        joinedload(OpcionComponenteServicio.producto_interno_ref) 
                    ).get(id_opcion_comp_form)

                    if opcion_obj_db:
                        cantidad_opcion_solicitada = Decimal(request.form.get(f'items[{item_idx}][componentes][{comp_idx}][cantidad_opcion_solicitada_cliente]', '1'))
                        
                        invitados_para_calculo_componente = Decimal(numero_invitados_item if numero_invitados_item is not None else (cotizacion_obj.numero_invitados_override or proyecto_para_repopular_original.numero_invitados or 1))

                        cantidad_final_calculada_para_bd = Decimal('0.0') 
                        variante_config_para_item = db.query(VarianteServicioConfig).options(
                            selectinload(VarianteServicioConfig.grupos_componentes)
                        ).get(id_variante_item) if id_variante_item else None

                        if variante_config_para_item and opcion_obj_db.id_grupo_config:
                            grupo_actual_config = next((g for g in variante_config_para_item.grupos_componentes if g.id_grupo_config == opcion_obj_db.id_grupo_config), None)
                            if grupo_actual_config:
                                cantidad_consumo_base_opcion = Decimal(opcion_obj_db.cantidad_consumo_base or '0.0')
                                cantidad_final_calculada_para_bd = cantidad_consumo_base_opcion * invitados_para_calculo_componente * cantidad_opcion_solicitada

                                if opcion_obj_db.producto_interno_ref and opcion_obj_db.producto_interno_ref.es_indivisible:
                                    cantidad_final_calculada_para_bd = Decimal(ceil(cantidad_final_calculada_para_bd))
                                elif opcion_obj_db.producto_interno_ref and not opcion_obj_db.producto_interno_ref.es_indivisible:
                                    if opcion_obj_db.producto_interno_ref.unidad_medida_base.lower() in ['g', 'ml']:
                                        cantidad_final_calculada_para_bd = (cantidad_final_calculada_para_bd / Decimal('5')).quantize(Decimal('1'), rounding=ROUND_CEILING) * Decimal('5')
                                        if cantidad_final_calculada_para_bd < (cantidad_consumo_base_opcion * invitados_para_calculo_componente * cantidad_opcion_solicitada):
                                            cantidad_final_calculada_para_bd = (((cantidad_consumo_base_opcion * invitados_para_calculo_componente * cantidad_opcion_solicitada) + Decimal('0.00001')) / Decimal('5')).quantize(Decimal('1'), rounding=ROUND_CEILING) * Decimal('5')
                            
                        nuevo_detalle_comp_sel = DetalleComponenteSeleccionado(
                            id_item_cotizacion=nuevo_item_cot.id_item_cotizacion,
                            id_opcion_componente=id_opcion_comp_form,
                            cantidad_opcion_solicitada_cliente=cantidad_opcion_solicitada,
                            cantidad_final_producto_interno_calc=cantidad_final_calculada_para_bd, 
                            precio_venta_seleccion_cliente_calc=(opcion_obj_db.costo_adicional_opcion or Decimal('0.00')) * cantidad_opcion_solicitada
                        )
                        db.add(nuevo_detalle_comp_sel)
                comp_idx += 1
            
            monto_total_servicios_calculado += (nuevo_item_cot.precio_total_item_calculado) 
            item_idx += 1
        
        cotizacion_obj.monto_servicios_productos = monto_total_servicios_calculado
        subtotal_con_logistica = cotizacion_obj.monto_servicios_productos + (cotizacion_obj.monto_costos_logisticos or Decimal('0.00'))
        cotizacion_obj.monto_subtotal_general = subtotal_con_logistica

        # Calcular y guardar montos de descuento e impuestos
        descuento_calculado = (subtotal_con_logistica * (cotizacion_obj.porcentaje_descuento_global / Decimal(100))).quantize(Decimal('0.01'), rounding=ROUND_DOWN) if cotizacion_obj.porcentaje_descuento_global is not None else Decimal('0.00')
        cotizacion_obj.monto_descuento_global = descuento_calculado
        
        base_para_impuestos = subtotal_con_logistica - descuento_calculado
        impuestos_calculados = (base_para_impuestos * (cotizacion_obj.porcentaje_impuestos / Decimal(100))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if cotizacion_obj.porcentaje_impuestos is not None else Decimal('0.00')
        cotizacion_obj.monto_impuestos = impuestos_calculados
        
        cotizacion_obj.monto_total_cotizado = base_para_impuestos + impuestos_calculados
        
        db.commit()
        flash(f"Cotización V{cotizacion_obj.version} para '{proyecto_para_repopular_original.nombre_evento}' guardada exitosamente.", "success")

        if accion == 'guardar_borrador':
            return redirect(url_for('cotizaciones_bp.vista_crear_cotizacion_paso2_configurar', id_cotizacion=cotizacion_obj.id_cotizacion))
        else: 
            return redirect(url_for('cotizaciones_bp.vista_ver_cotizacion', id_cotizacion=cotizacion_obj.id_cotizacion))

    except ValueError as ve: 
        if db.is_active: db.rollback()
        flash(f"Error en los datos del formulario de cotización: {str(ve)}", "danger")
    except Exception as e: 
        if db.is_active: db.rollback()
        flash(f"Error al guardar la cotización: {str(e)}", "danger")
        import traceback
        traceback.print_exc()
    finally:
        if db.is_active:
            db.close() 

    db_repopulate = SessionLocal() 
    proyecto_repop_final = None
    cotizacion_display_repop = None
    try:
        if id_proyecto_form:
            proyecto_repop_final = db_repopulate.query(Proyecto).get(id_proyecto_form)
        
        if not proyecto_repop_final: 
             flash("Error crítico: No se pudo recargar el proyecto para mostrar el formulario de error.", "danger")
             return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones'))

        tipos_servicio_base_activos_repop = db_repopulate.query(TipoServicioBase)\
                                            .filter(TipoServicioBase.activo == True)\
                                            .order_by(TipoServicioBase.nombre)\
                                            .all()
        
        todas_variantes_obj_repop = db_repopulate.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref)
        ).filter(VarianteServicioConfig.activo==True).order_by(VarianteServicioConfig.id_tipo_servicio_base, VarianteServicioConfig.nombre_variante).all()
        
        todas_variantes_config_serializable_repop = []
        for variante_repop in todas_variantes_obj_repop:
            todas_variantes_config_serializable_repop.append({
                "id_variante_config": variante_repop.id_variante_config,
                "nombre_variante": variante_repop.nombre_variante,
                "id_tipo_servicio_base": variante_repop.id_tipo_servicio_base,
                "nombre_tipo_servicio_base": variante_repop.tipo_servicio_base_ref.nombre if variante_repop.tipo_servicio_base_ref else None,
                "nivel_paquete": variante_repop.nivel_paquete,
                "nivel_perfil": variante_repop.nivel_perfil,
                "precio_base_sugerido": float(variante_repop.precio_base_sugerido) if variante_repop.precio_base_sugerido is not None else None
            })
        
        if id_cotizacion_existente: 
            cotizacion_display_repop = db_repopulate.query(Cotizacion).options(
                 joinedload(Cotizacion.proyecto), 
                 selectinload(Cotizacion.items_cotizacion).options(
                    selectinload(ItemCotizacion.variante_servicio_config_usada),
                    selectinload(ItemCotizacion.componentes_seleccionados).options(
                        selectinload(DetalleComponenteSeleccionado.opcion_componente_elegida).options(
                            selectinload(OpcionComponenteServicio.producto_interno_ref)
                        )
                    )
                )
            ).get(id_cotizacion_existente)
        elif cotizacion_para_repopular_original: 
            cotizacion_display_repop = cotizacion_para_repopular_original 
            if not hasattr(cotizacion_display_repop, 'items_cotizacion'): 
                 cotizacion_display_repop.items_cotizacion = []


        titulo_repop = f"Revisar Cotización para: {proyecto_repop_final.nombre_evento if proyecto_repop_final else 'Proyecto Desconocido'}"

        return render_template('configurar_cotizacion.html',
                               proyecto=proyecto_repop_final, 
                               cotizacion=cotizacion_display_repop, 
                               es_nueva_cotizacion=(not id_cotizacion_existente),
                               fecha_hoy=date.today().isoformat(),
                               todos_tipos_servicio_base_activos=tipos_servicio_base_activos_repop,
                               todas_variantes_config=todas_variantes_config_serializable_repop, 
                               titulo_pagina=titulo_repop,
                               enumerate=enumerate)
    except Exception as e_repop:
        flash(f"Error adicional al intentar repopular el formulario: {str(e_repop)}", "danger")
        if id_cotizacion_existente:
            return redirect(url_for('cotizaciones_bp.vista_crear_cotizacion_paso2_configurar', id_cotizacion=id_cotizacion_existente))
        elif id_proyecto_form:
            return redirect(url_for('cotizaciones_bp.vista_crear_cotizacion_paso2_configurar', id_proyecto=id_proyecto_form))
        else:
            return redirect(url_for('cotizaciones_bp.vista_crear_cotizacion_paso1_proyecto'))
    finally:
        if db_repopulate.is_active:
            db_repopulate.close()


@cotizaciones_bp.route('/<int:id_cotizacion>/ver', methods=['GET'])
def vista_ver_cotizacion(id_cotizacion):
    db = SessionLocal()
    try:
        cotizacion = db.query(Cotizacion).options(
            joinedload(Cotizacion.proyecto), 
            selectinload(Cotizacion.items_cotizacion).options( 
                selectinload(ItemCotizacion.variante_servicio_config_usada), 
                selectinload(ItemCotizacion.componentes_seleccionados).options( 
                    selectinload(DetalleComponenteSeleccionado.opcion_componente_elegida).options( 
                        selectinload(OpcionComponenteServicio.producto_interno_ref) 
                    )
                )
            )
        ).get(id_cotizacion)
        
        if not cotizacion:
            flash("Cotización no encontrada.", "danger")
            return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones'))

        titulo = f"Cotización V{cotizacion.version} - {cotizacion.proyecto.nombre_evento}"
        return render_template('ver_cotizacion_publica.html',
                               cotizacion=cotizacion,
                               titulo_pagina=titulo)
    except Exception as e:
        flash(f"Error al cargar la cotización para ver: {str(e)}", "danger")
        import traceback 
        traceback.print_exc()
        return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones'))
    finally:
        if db.is_active:
            db.close()

@cotizaciones_bp.route('/nueva/integral', methods=['GET', 'POST'])
def vista_crear_evento_cotizacion_integral():
    db = SessionLocal()
    try:
        tipos_servicio_base_activos = db.query(TipoServicioBase)\
                                        .filter(TipoServicioBase.activo == True)\
                                        .order_by(TipoServicioBase.nombre)\
                                        .all()
        
        todas_variantes_obj_list_integral = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref)
        ).filter(VarianteServicioConfig.activo==True).order_by(VarianteServicioConfig.id_tipo_servicio_base, VarianteServicioConfig.nombre_variante).all()
        
        todas_variantes_config_serializable_integral = []
        for variante_int in todas_variantes_obj_list_integral:
            todas_variantes_config_serializable_integral.append({
                "id_variante_config": variante_int.id_variante_config,
                "nombre_variante": variante_int.nombre_variante,
                "id_tipo_servicio_base": variante_int.id_tipo_servicio_base,
                "nombre_tipo_servicio_base": variante_int.tipo_servicio_base_ref.nombre if variante_int.tipo_servicio_base_ref else None,
                "nivel_paquete": variante_int.nivel_paquete,
                "nivel_perfil": variante_int.nivel_perfil,
                "precio_base_sugerido": float(variante_int.precio_base_sugerido) if variante_int.precio_base_sugerido is not None else None
            })


        if request.method == 'POST':
            identificador_evento_form = request.form.get('identificador_evento', '').strip()
            nombre_evento_form = request.form.get('nombre_evento', '').strip()
            fecha_evento_str = request.form.get('fecha_evento')
            numero_invitados_proyecto_str = request.form.get('numero_invitados_proyecto')
            cliente_nombre_form = request.form.get('cliente_nombre', '').strip()
            cliente_telefono_form = request.form.get('cliente_telefono', '').strip()
            cliente_email_form = request.form.get('cliente_email', '').strip()
            direccion_evento_form = request.form.get('direccion_evento', '').strip()
            tipo_ubicacion_form = request.form.get('tipo_ubicacion', 'Local (CDMX y Área Metropolitana)')
            
            # Leer costos logísticos directamente como montos, ya que el form los tiene así
            costo_transporte_form = Decimal(request.form.get('costo_transporte_cotizacion', '0.00'))
            costo_viaticos_form = Decimal(request.form.get('costo_viaticos_cotizacion', '0.00'))
            costo_hospedaje_form = Decimal(request.form.get('costo_hospedaje_cotizacion', '0.00'))
            monto_total_costos_logisticos_form = costo_transporte_form + costo_viaticos_form + costo_hospedaje_form

            notas_proyecto_form = request.form.get('notas_proyecto', '').strip()

            errores_proyecto = []
            if not identificador_evento_form: errores_proyecto.append("Identificador del Evento es obligatorio.")
            if not nombre_evento_form: errores_proyecto.append("Nombre del Evento es obligatorio.")
            if not fecha_evento_str: errores_proyecto.append("Fecha del Evento es obligatoria.")
            
            if errores_proyecto:
                for error in errores_proyecto: flash(error, "danger")
                return render_template('crear_evento_cotizacion_integral.html',
                                       todos_tipos_servicio_base_activos=tipos_servicio_base_activos,
                                       todas_variantes_config=todas_variantes_config_serializable_integral, 
                                       form_data=request.form, 
                                       fecha_hoy=date.today().isoformat(),
                                       titulo_pagina="Nuevo Evento y Cotización (Corregir Errores)")

            existente = db.query(Proyecto).filter(Proyecto.identificador_evento == identificador_evento_form).first()
            if existente:
                flash(f"El Identificador del Evento '{identificador_evento_form}' ya existe. Elige otro.", "warning")
                return render_template('crear_evento_cotizacion_integral.html',
                                       todos_tipos_servicio_base_activos=tipos_servicio_base_activos,
                                       todas_variantes_config=todas_variantes_config_serializable_integral, 
                                       form_data=request.form,
                                       fecha_hoy=date.today().isoformat(),
                                       titulo_pagina="Nuevo Evento y Cotización (Identificador Duplicado)")
            
            try:
                fecha_evento_obj = date.fromisoformat(fecha_evento_str)
                numero_invitados_proyecto_obj = int(numero_invitados_proyecto_str) if numero_invitados_proyecto_str and numero_invitados_proyecto_str.isdigit() else 1
            except ValueError:
                flash("Formato de fecha o número de invitados del proyecto inválido.", "danger")
                return render_template('crear_evento_cotizacion_integral.html',
                                       todos_tipos_servicio_base_activos=tipos_servicio_base_activos,
                                       todas_variantes_config=todas_variantes_config_serializable_integral, 
                                       form_data=request.form,
                                       fecha_hoy=date.today().isoformat(),
                                       titulo_pagina="Nuevo Evento y Cotización (Error de Formato)")

            nuevo_proyecto = Proyecto(
                identificador_evento=identificador_evento_form,
                nombre_evento=nombre_evento_form,
                fecha_evento=fecha_evento_obj,
                numero_invitados=numero_invitados_proyecto_obj,
                cliente_nombre=cliente_nombre_form,
                cliente_telefono=cliente_telefono_form,
                cliente_email=cliente_email_form,
                direccion_evento=direccion_evento_form,
                tipo_ubicacion=tipo_ubicacion_form,
                costo_transporte_estimado=costo_transporte_form, # Usar el valor del form de cotización
                costo_viaticos_estimado=costo_viaticos_form,     # Usar el valor del form de cotización
                costo_hospedaje_estimado=costo_hospedaje_form,   # Usar el valor del form de cotización
                notas_proyecto=notas_proyecto_form
            )
            db.add(nuevo_proyecto)
            db.flush() 

            numero_invitados_cotizacion_str = request.form.get('numero_invitados_cotizacion_override_integral', str(nuevo_proyecto.numero_invitados)) 
            numero_invitados_cotizacion = int(numero_invitados_cotizacion_str) if numero_invitados_cotizacion_str and numero_invitados_cotizacion_str.isdigit() else nuevo_proyecto.numero_invitados or 1
            
            fecha_emision_cot_str = request.form.get('fecha_emision_cotizacion', date.today().isoformat())
            fecha_validez_cot_str = request.form.get('fecha_validez_cotizacion')
            
            try:
                fecha_emision_cot_obj = date.fromisoformat(fecha_emision_cot_str)
                fecha_validez_cot_obj = date.fromisoformat(fecha_validez_cot_str) if fecha_validez_cot_str else None
            except ValueError:
                flash("Formato de fecha de emisión o validez de cotización inválido.", "danger")
                db.rollback() 
                return render_template('crear_evento_cotizacion_integral.html',
                                       todos_tipos_servicio_base_activos=tipos_servicio_base_activos,
                                       todas_variantes_config=todas_variantes_config_serializable_integral, 
                                       form_data=request.form,
                                       fecha_hoy=date.today().isoformat(),
                                       titulo_pagina="Nuevo Evento y Cotización (Error Fecha Cot.)")
            
            # Leer porcentajes del form para la cotización
            porcentaje_desc_cot_str = request.form.get('porcentaje_descuento_global_cotizacion', '0.00')
            porcentaje_imp_cot_str = request.form.get('porcentaje_impuestos_cotizacion', '16.00')
            try:
                porcentaje_desc_cot_form = Decimal(porcentaje_desc_cot_str) if porcentaje_desc_cot_str else Decimal('0.00')
                porcentaje_imp_cot_form = Decimal(porcentaje_imp_cot_str) if porcentaje_imp_cot_str else Decimal('0.00')
            except InvalidOperation:
                flash("Formato de porcentaje de descuento o impuestos inválido para la cotización.", "danger")
                db.rollback()
                return render_template('crear_evento_cotizacion_integral.html',
                                       todos_tipos_servicio_base_activos=tipos_servicio_base_activos,
                                       todas_variantes_config=todas_variantes_config_serializable_integral,
                                       form_data=request.form,
                                       fecha_hoy=date.today().isoformat(),
                                       titulo_pagina="Nuevo Evento y Cotización (Error Porcentaje)")


            nueva_cotizacion = Cotizacion(
                id_proyecto=nuevo_proyecto.id_proyecto,
                version=1, 
                fecha_emision=fecha_emision_cot_obj,
                fecha_validez=fecha_validez_cot_obj,
                estado=request.form.get('estado_cotizacion', 'Borrador'),
                numero_invitados_override=numero_invitados_cotizacion if numero_invitados_cotizacion != nuevo_proyecto.numero_invitados else None,
                monto_costos_logisticos=monto_total_costos_logisticos_form, 
                porcentaje_descuento_global=porcentaje_desc_cot_form, # Guardar porcentaje
                porcentaje_impuestos=porcentaje_imp_cot_form,       # Guardar porcentaje
                terminos_condiciones=request.form.get('terminos_condiciones_cotizacion'),
                notas_cotizacion=request.form.get('notas_cotizacion_internas')
            )
            db.add(nueva_cotizacion)
            db.flush() 

            monto_total_servicios_calculado = Decimal('0.00')
            item_idx = 0
            while f'items[{item_idx}][nombre_display_servicio]' in request.form:
                nombre_display_item = request.form.get(f'items[{item_idx}][nombre_display_servicio]')
                id_variante_item_str = request.form.get(f'items[{item_idx}][id_variante_servicio_config]')
                id_variante_item = int(id_variante_item_str) if id_variante_item_str and id_variante_item_str.isdigit() else None
                cantidad_servicio_str = request.form.get(f'items[{item_idx}][cantidad_servicio]', '1.0')
                cantidad_servicio = Decimal(cantidad_servicio_str) if cantidad_servicio_str else Decimal('1.0')
                descripcion_item = request.form.get(f'items[{item_idx}][descripcion_servicio_cotizado]')
                precio_total_item_calculado_form = Decimal(request.form.get(f'items[{item_idx}][precio_total_item_calculado]', '0.00'))
                
                numero_invitados_item_form = request.form.get(f'items[{item_idx}][numero_invitados_servicio_item]')
                numero_invitados_item_obj = int(numero_invitados_item_form) if numero_invitados_item_form and numero_invitados_item_form.isdigit() else None


                nuevo_item_cot = ItemCotizacion(
                    id_cotizacion=nueva_cotizacion.id_cotizacion,
                    id_variante_servicio_config=id_variante_item,
                    nombre_display_servicio=nombre_display_item,
                    descripcion_servicio_cotizado=descripcion_item,
                    cantidad_servicio=cantidad_servicio,
                    precio_total_item_calculado = precio_total_item_calculado_form,
                    numero_invitados_servicio_item=numero_invitados_item_obj 
                )
                db.add(nuevo_item_cot)
                db.flush()
                
                comp_idx = 0
                while f'items[{item_idx}][componentes][{comp_idx}][id_opcion_componente]' in request.form:
                    id_opcion_comp_form_str = request.form[f'items[{item_idx}][componentes][{comp_idx}][id_opcion_componente]']
                    if id_opcion_comp_form_str and id_opcion_comp_form_str.isdigit():
                        id_opcion_comp_form = int(id_opcion_comp_form_str)
                        opcion_obj_db = db.query(OpcionComponenteServicio).options(
                            joinedload(OpcionComponenteServicio.producto_interno_ref)
                        ).get(id_opcion_comp_form)

                        if opcion_obj_db:
                            cantidad_opcion_solicitada = Decimal(request.form.get(f'items[{item_idx}][componentes][{comp_idx}][cantidad_opcion_solicitada_cliente]', '1'))
                            
                            invitados_para_calculo_comp = Decimal(numero_invitados_item_obj if numero_invitados_item_obj is not None else nueva_cotizacion.numero_invitados_override or nuevo_proyecto.numero_invitados or 1)

                            cantidad_final_calculada_para_bd = Decimal('0.0') 
                            variante_config_para_item = db.query(VarianteServicioConfig).options(
                                selectinload(VarianteServicioConfig.grupos_componentes)
                            ).get(id_variante_item) if id_variante_item else None

                            if variante_config_para_item and opcion_obj_db.id_grupo_config:
                                grupo_actual_config = next((g for g in variante_config_para_item.grupos_componentes if g.id_grupo_config == opcion_obj_db.id_grupo_config), None)
                                if grupo_actual_config:
                                    cantidad_consumo_base_opcion = Decimal(opcion_obj_db.cantidad_consumo_base or '0.0')
                                    cantidad_final_calculada_para_bd = cantidad_consumo_base_opcion * invitados_para_calculo_comp * cantidad_opcion_solicitada

                                    if opcion_obj_db.producto_interno_ref and opcion_obj_db.producto_interno_ref.es_indivisible:
                                        cantidad_final_calculada_para_bd = Decimal(ceil(cantidad_final_calculada_para_bd))
                                    elif opcion_obj_db.producto_interno_ref and not opcion_obj_db.producto_interno_ref.es_indivisible:
                                        if opcion_obj_db.producto_interno_ref.unidad_medida_base.lower() in ['g', 'ml']:
                                            cantidad_final_calculada_para_bd = (cantidad_final_calculada_para_bd / Decimal('5')).quantize(Decimal('1'), rounding=ROUND_CEILING) * Decimal('5')
                                            if cantidad_final_calculada_para_bd < (cantidad_consumo_base_opcion * invitados_para_calculo_comp * cantidad_opcion_solicitada):
                                                cantidad_final_calculada_para_bd = (((cantidad_consumo_base_opcion * invitados_para_calculo_comp * cantidad_opcion_solicitada) + Decimal('0.00001')) / Decimal('5')).quantize(Decimal('1'), rounding=ROUND_CEILING) * Decimal('5')
                            
                            nuevo_detalle_comp_sel = DetalleComponenteSeleccionado(
                                id_item_cotizacion=nuevo_item_cot.id_item_cotizacion,
                                id_opcion_componente=id_opcion_comp_form,
                                cantidad_opcion_solicitada_cliente=cantidad_opcion_solicitada,
                                cantidad_final_producto_interno_calc=cantidad_final_calculada_para_bd,
                                precio_venta_seleccion_cliente_calc=(opcion_obj_db.costo_adicional_opcion or Decimal('0.00')) * cantidad_opcion_solicitada
                            )
                            db.add(nuevo_detalle_comp_sel)
                    comp_idx += 1
                
                monto_total_servicios_calculado += (nuevo_item_cot.precio_total_item_calculado)
                item_idx += 1

            nueva_cotizacion.monto_servicios_productos = monto_total_servicios_calculado
            subtotal_con_logistica_integral = nueva_cotizacion.monto_servicios_productos + (nueva_cotizacion.monto_costos_logisticos or Decimal('0.00'))
            nueva_cotizacion.monto_subtotal_general = subtotal_con_logistica_integral

            descuento_calculado_integral = (subtotal_con_logistica_integral * (nueva_cotizacion.porcentaje_descuento_global / Decimal(100))).quantize(Decimal('0.01'), rounding=ROUND_DOWN) if nueva_cotizacion.porcentaje_descuento_global is not None else Decimal('0.00')
            nueva_cotizacion.monto_descuento_global = descuento_calculado_integral
            
            base_para_impuestos_integral = subtotal_con_logistica_integral - descuento_calculado_integral
            impuestos_calculados_integral = (base_para_impuestos_integral * (nueva_cotizacion.porcentaje_impuestos / Decimal(100))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if nueva_cotizacion.porcentaje_impuestos is not None else Decimal('0.00')
            nueva_cotizacion.monto_impuestos = impuestos_calculados_integral
            
            nueva_cotizacion.monto_total_cotizado = base_para_impuestos_integral + impuestos_calculados_integral
            
            db.commit()
            flash(f"Evento '{nuevo_proyecto.nombre_evento}' y Cotización V1 creados exitosamente.", "success")
            return redirect(url_for('cotizaciones_bp.vista_ver_cotizacion', id_cotizacion=nueva_cotizacion.id_cotizacion))

        # Para GET
        return render_template('crear_evento_cotizacion_integral.html',
                               todos_tipos_servicio_base_activos=tipos_servicio_base_activos,
                               todas_variantes_config=todas_variantes_config_serializable_integral, 
                               form_data={}, 
                               fecha_hoy=date.today().isoformat(),
                               titulo_pagina="Nuevo Evento y Cotización Integral")
    except Exception as e:
        if db and db.is_active: db.rollback()
        flash(f"Error al procesar la creación integral: {str(e)}", "danger")
        import traceback
        traceback.print_exc()
        return render_template('crear_evento_cotizacion_integral.html',
                               todos_tipos_servicio_base_activos=tipos_servicio_base_activos if 'tipos_servicio_base_activos' in locals() else [],
                               todas_variantes_config=todas_variantes_config_serializable_integral if 'todas_variantes_config_serializable_integral' in locals() else [], 
                               form_data=request.form if request.method == 'POST' else {},
                               fecha_hoy=date.today().isoformat(),
                               titulo_pagina="Nuevo Evento y Cotización (Error)")
    finally:
        if db and db.is_active:
            db.close()
