# /mod_cotizaciones/routes.py
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, distinct
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP 
from datetime import date
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
                estado="Borrador"
            )
            if proyecto:
                cotizacion_obj_para_template.monto_costos_logisticos = (proyecto.costo_transporte_estimado or Decimal('0.0')) + \
                                                                      (proyecto.costo_viaticos_estimado or Decimal('0.0')) + \
                                                                      (proyecto.costo_hospedaje_estimado or Decimal('0.0'))
            titulo = f"Nueva Cotización (V{nueva_version}) para: {proyecto.nombre_evento}"
        
        else:
            flash("Se requiere un proyecto o una cotización existente.", "danger")
            return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones'))

        todas_variantes_config_activas = db.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref)
        ).filter(VarianteServicioConfig.activo==True).order_by(VarianteServicioConfig.id_tipo_servicio_base, VarianteServicioConfig.nombre_variante).all()

        return render_template('configurar_cotizacion.html',
                               proyecto=proyecto,
                               cotizacion=cotizacion_obj_para_template,
                               es_nueva_cotizacion=es_nueva_cotizacion,
                               fecha_hoy=fecha_hoy_iso,
                               todos_tipos_servicio_base_activos=tipos_servicio_base_activos,
                               todas_variantes_config=todas_variantes_config_activas,
                               titulo_pagina=titulo,
                               enumerate=enumerate) 
    except Exception as e:
        flash(f"Error al preparar la configuración de la cotización: {str(e)}", "danger")
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
        numero_invitados_para_calculo = Decimal(numero_invitados_cotizacion if numero_invitados_cotizacion is not None else proyecto_para_repopular_original.numero_invitados or 1)

        accion = request.form.get('accion', 'guardar_borrador')
        fecha_emision_form = date.fromisoformat(request.form.get('fecha_emision'))
        fecha_validez_form_str = request.form.get('fecha_validez')
        fecha_validez_form = date.fromisoformat(fecha_validez_form_str) if fecha_validez_form_str else None
        estado_form = request.form.get('estado', 'Borrador')
        monto_costos_logisticos = Decimal(request.form.get('monto_costos_logisticos', '0.00'))
        monto_descuento_global = Decimal(request.form.get('monto_descuento_global', '0.00'))
        monto_impuestos = Decimal(request.form.get('monto_impuestos', '0.00'))
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
            cotizacion_obj.monto_costos_logisticos = monto_costos_logisticos
            cotizacion_obj.monto_descuento_global = monto_descuento_global
            cotizacion_obj.monto_impuestos = monto_impuestos
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
                monto_costos_logisticos=monto_costos_logisticos,
                monto_descuento_global=monto_descuento_global,
                monto_impuestos=monto_impuestos,
                terminos_condiciones=terminos_condiciones_form,
                notas_cotizacion=notas_cotizacion_form
            )
            db.add(cotizacion_obj)
            db.flush() 

        cotizacion_para_repopular_original = cotizacion_obj 

        if id_cotizacion_existente:
            items_a_eliminar = db.query(ItemCotizacion).filter_by(id_cotizacion=id_cotizacion_existente).all()
            for item_viejo in items_a_eliminar:
                db.delete(item_viejo)
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

            nuevo_item_cot = ItemCotizacion(
                id_cotizacion=cotizacion_obj.id_cotizacion,
                id_variante_servicio_config=id_variante_item,
                nombre_display_servicio=nombre_display_item,
                descripcion_servicio_cotizado=descripcion_item,
                cantidad_servicio=cantidad_servicio,
                precio_total_item_calculado = precio_total_item_calculado_form 
            )
            db.add(nuevo_item_cot)
            db.flush() 

            precio_total_componentes_para_este_item = Decimal('0.00')
            
            variante_config_para_item = None
            if id_variante_item:
                variante_config_para_item = db.query(VarianteServicioConfig).options(
                    selectinload(VarianteServicioConfig.grupos_componentes) 
                ).get(id_variante_item)

            if variante_config_para_item: 
                total_grupos_disponibles_en_variante = len(variante_config_para_item.grupos_componentes)
                selecciones_form_por_grupo = {}
                
                form_component_idx = 0 
                while f'items[{item_idx}][componentes][{form_component_idx}][id_opcion_componente]' in request.form:
                    id_opcion_comp_form_str = request.form[f'items[{item_idx}][componentes][{form_component_idx}][id_opcion_componente]']
                    if id_opcion_comp_form_str and id_opcion_comp_form_str.isdigit():
                        id_opcion_comp_form = int(id_opcion_comp_form_str)
                        opcion_obj_para_grupo = db.query(OpcionComponenteServicio).get(id_opcion_comp_form)
                        if opcion_obj_para_grupo:
                            id_grupo_real = opcion_obj_para_grupo.id_grupo_config
                            if id_grupo_real not in selecciones_form_por_grupo:
                                selecciones_form_por_grupo[id_grupo_real] = []
                            selecciones_form_por_grupo[id_grupo_real].append({
                                "id_opcion_componente": id_opcion_comp_form,
                                "cantidad_opcion_solicitada_cliente": Decimal(request.form.get(f'items[{item_idx}][componentes][{form_component_idx}][cantidad_opcion_solicitada_cliente]', '1'))
                            })
                    form_component_idx += 1
                
                numero_de_grupos_con_selecciones_en_variante = len(selecciones_form_por_grupo)
                factor_ajuste_global_de_grupos = Decimal('1.0')
                if numero_de_grupos_con_selecciones_en_variante > 0 and total_grupos_disponibles_en_variante > 0 and \
                   numero_de_grupos_con_selecciones_en_variante < total_grupos_disponibles_en_variante:
                    factor_ajuste_global_de_grupos = Decimal(total_grupos_disponibles_en_variante) / Decimal(numero_de_grupos_con_selecciones_en_variante)

                for grupo_config in variante_config_para_item.grupos_componentes:
                    opciones_seleccionadas_para_este_grupo_form = selecciones_form_por_grupo.get(grupo_config.id_grupo_config, [])
                    num_opciones_realmente_elegidas_en_grupo = len(opciones_seleccionadas_para_este_grupo_form)

                    if num_opciones_realmente_elegidas_en_grupo == 0:
                        continue

                    factor_ajuste_intra_grupo = Decimal(grupo_config.cantidad_opciones_seleccionables) / Decimal(num_opciones_realmente_elegidas_en_grupo)

                    for seleccion_comp_form in opciones_seleccionadas_para_este_grupo_form:
                        opcion_servicio = db.query(OpcionComponenteServicio).options(
                            joinedload(OpcionComponenteServicio.producto_interno_ref) # Asegurar que el producto se carga
                        ).get(seleccion_comp_form["id_opcion_componente"])

                        if not opcion_servicio or opcion_servicio.cantidad_consumo_base is None:
                            continue
                        
                        cantidad_consumo_base_opcion = Decimal(opcion_servicio.cantidad_consumo_base)
                        cantidad_ajustada_bruta = cantidad_consumo_base_opcion * factor_ajuste_intra_grupo * factor_ajuste_global_de_grupos
                        cantidad_ajustada_persona_final = cantidad_ajustada_bruta
                        cantidad_total_evento_final_prod = cantidad_ajustada_persona_final * numero_invitados_para_calculo
                        
                        # Lógica de redondeo para cantidad_final_producto_interno_calc
                        # Se aplica el redondeo aquí para que se guarde el valor correcto.
                        if opcion_servicio.producto_interno_ref and opcion_servicio.producto_interno_ref.es_indivisible:
                             cantidad_total_evento_final_prod = Decimal(ceil(cantidad_total_evento_final_prod))
                        elif opcion_servicio.producto_interno_ref and not opcion_servicio.producto_interno_ref.es_indivisible:
                            # Redondear a múltiplos de 5g (o la lógica que prefieras)
                            cantidad_total_evento_final_prod = (cantidad_total_evento_final_prod / Decimal('5')).quantize(Decimal('1'), rounding=ROUND_CEILING) * Decimal('5')
                            if cantidad_total_evento_final_prod < (cantidad_ajustada_persona_final * numero_invitados_para_calculo) : 
                                cantidad_total_evento_final_prod = (( (cantidad_ajustada_persona_final * numero_invitados_para_calculo) + Decimal('0.00001')) / Decimal('5')).quantize(Decimal('1'), rounding=ROUND_CEILING) * Decimal('5')
                        # Si no es un producto interno (opción directa), la cantidad_total_evento_final_prod ya es la cantidad de la opción.
                        
                        precio_componente_actual = Decimal(opcion_servicio.costo_adicional_opcion or '0.00')
                        
                        nuevo_detalle_comp_sel = DetalleComponenteSeleccionado(
                            id_item_cotizacion=nuevo_item_cot.id_item_cotizacion,
                            id_opcion_componente=opcion_servicio.id_opcion_componente,
                            cantidad_opcion_solicitada_cliente=seleccion_comp_form["cantidad_opcion_solicitada_cliente"],
                            # MODIFICACIÓN CLAVE: Guardar siempre la cantidad calculada
                            cantidad_final_producto_interno_calc=cantidad_total_evento_final_prod,
                            precio_venta_seleccion_cliente_calc=precio_componente_actual * seleccion_comp_form["cantidad_opcion_solicitada_cliente"]
                        )
                        db.add(nuevo_detalle_comp_sel)
                        precio_total_componentes_para_este_item += nuevo_detalle_comp_sel.precio_venta_seleccion_cliente_calc
                
                nuevo_item_cot.precio_total_item_calculado = precio_total_componentes_para_este_item
            
            monto_total_servicios_calculado += (nuevo_item_cot.precio_total_item_calculado * nuevo_item_cot.cantidad_servicio)
            item_idx += 1
        
        cotizacion_obj.monto_servicios_productos = monto_total_servicios_calculado
        cotizacion_obj.monto_subtotal_general = cotizacion_obj.monto_servicios_productos + (cotizacion_obj.monto_costos_logisticos or Decimal('0.00'))
        cotizacion_obj.monto_total_cotizado = cotizacion_obj.monto_subtotal_general - \
                                             (cotizacion_obj.monto_descuento_global or Decimal('0.00')) + \
                                             (cotizacion_obj.monto_impuestos or Decimal('0.00'))
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
        todas_variantes_config_activas_repop = db_repopulate.query(VarianteServicioConfig).options(
            joinedload(VarianteServicioConfig.tipo_servicio_base_ref)
        ).filter(VarianteServicioConfig.activo==True).order_by(VarianteServicioConfig.id_tipo_servicio_base, VarianteServicioConfig.nombre_variante).all()
        
        if id_cotizacion_existente:
            cotizacion_display_repop = db_repopulate.query(Cotizacion).options(
                 joinedload(Cotizacion.proyecto), 
                 selectinload(Cotizacion.items_cotizacion).options( # Cargar ítems y sus componentes para repopular
                    selectinload(ItemCotizacion.variante_servicio_config_usada),
                    selectinload(ItemCotizacion.componentes_seleccionados).options(
                        selectinload(DetalleComponenteSeleccionado.opcion_componente_elegida).options(
                            selectinload(OpcionComponenteServicio.producto_interno_ref)
                        )
                    )
                )
            ).get(id_cotizacion_existente)
        elif cotizacion_para_repopular_original: 
            cotizacion_display_repop = cotizacion_para_repopular_original # Usar el objeto temporal si era nuevo
            # Para repopular los ítems si era una creación fallida, necesitarías reconstruirlos
            # desde request.form, lo cual es más complejo. Por ahora, se mostrará sin ítems si falló la creación.
            if not hasattr(cotizacion_display_repop, 'items_cotizacion'):
                 cotizacion_display_repop.items_cotizacion = []


        titulo_repop = f"Revisar Cotización para: {proyecto_repop_final.nombre_evento if proyecto_repop_final else 'Proyecto Desconocido'}"

        return render_template('configurar_cotizacion.html',
                               proyecto=proyecto_repop_final, 
                               cotizacion=cotizacion_display_repop, 
                               es_nueva_cotizacion=(not id_cotizacion_existente),
                               fecha_hoy=date.today().isoformat(),
                               todos_tipos_servicio_base_activos=tipos_servicio_base_activos_repop,
                               todas_variantes_config=todas_variantes_config_activas_repop,
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
