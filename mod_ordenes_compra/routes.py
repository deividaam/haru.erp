# /mod_ordenes_compra/routes.py
from flask import render_template, request, redirect, url_for, flash
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, func as sqlfunc
from decimal import Decimal, ROUND_UP
import math
from collections import defaultdict
from datetime import date

from . import ordenes_compra_bp
from database import SessionLocal
from models import (
    Cotizacion, ItemCotizacion, DetalleComponenteSeleccionado,
    OpcionComponenteServicio, Producto, Proveedor, PrecioProveedor
)

def seleccionar_mejor_precio_proveedor(db_session: Session, producto_id: int, cantidad_necesaria_base: Decimal):
    """
    Selecciona el mejor proveedor y precio para un producto dado.
    Devuelve el objeto Proveedor, el objeto PrecioProveedor, la cantidad de presentaciones a comprar y el costo.
    """
    print(f"DEBUG_PRECIO: Buscando precio para Producto ID: {producto_id}, Cantidad Base: {cantidad_necesaria_base}")
    producto = db_session.query(Producto).get(producto_id)
    if not producto:
        print(f"DEBUG_PRECIO: Producto ID {producto_id} no encontrado.")
        return None, None, Decimal('0'), Decimal('0.00'), "Producto no encontrado"

    query_precios = db_session.query(PrecioProveedor).filter(
        PrecioProveedor.id_producto == producto_id
    ).order_by(PrecioProveedor.precio_compra.asc())

    mejor_opcion_precio_proveedor_obj = None
    
    if producto.presentacion_compra:
        precios_con_presentacion_definida = query_precios.filter(
            PrecioProveedor.unidad_compra_proveedor == producto.presentacion_compra
        ).all()
        if precios_con_presentacion_definida:
            mejor_opcion_precio_proveedor_obj = precios_con_presentacion_definida[0]
            print(f"DEBUG_PRECIO: Encontrado precio con presentación definida: {mejor_opcion_precio_proveedor_obj.id_precio_proveedor}")

    if not mejor_opcion_precio_proveedor_obj:
        todos_los_precios = query_precios.all()
        if todos_los_precios:
            mejor_opcion_precio_proveedor_obj = todos_los_precios[0]
            print(f"DEBUG_PRECIO: Encontrado mejor precio general: {mejor_opcion_precio_proveedor_obj.id_precio_proveedor}")
        else:
            print(f"DEBUG_PRECIO: No se encontraron precios para Producto ID: {producto_id}")
            return None, None, Decimal('0'), Decimal('0.00'), "Proveedor/Precio no encontrado"

    proveedor_seleccionado_obj = db_session.query(Proveedor).get(mejor_opcion_precio_proveedor_obj.id_proveedor)
    print(f"DEBUG_PRECIO: Proveedor seleccionado: {proveedor_seleccionado_obj.nombre_proveedor if proveedor_seleccionado_obj else 'Desconocido'}")


    cantidad_por_presentacion_proveedor = Decimal('1.0')
    unidad_compra_proveedor_display = mejor_opcion_precio_proveedor_obj.unidad_compra_proveedor or producto.presentacion_compra or producto.unidad_medida_base
    
    if producto.cantidad_en_presentacion_compra and producto.presentacion_compra and \
       mejor_opcion_precio_proveedor_obj.unidad_compra_proveedor == producto.presentacion_compra:
        cantidad_por_presentacion_proveedor = Decimal(producto.cantidad_en_presentacion_compra)
    elif producto.unidad_medida_base and mejor_opcion_precio_proveedor_obj.unidad_compra_proveedor and \
         producto.unidad_medida_base.lower() == mejor_opcion_precio_proveedor_obj.unidad_compra_proveedor.lower():
         cantidad_por_presentacion_proveedor = Decimal('1.0')
    else:
        if mejor_opcion_precio_proveedor_obj.unidad_compra_proveedor and producto.unidad_medida_base:
            ucp_lower = mejor_opcion_precio_proveedor_obj.unidad_compra_proveedor.lower()
            umb_lower = producto.unidad_medida_base.lower()
            if "kg" in ucp_lower and "g" in umb_lower:
                try:
                    num_kg_str = ''.join(filter(lambda x: x.isdigit() or x == '.', ucp_lower.split('kg')[0].strip()))
                    num_kg = Decimal(num_kg_str) if num_kg_str else Decimal('1')
                    cantidad_por_presentacion_proveedor = num_kg * Decimal('1000')
                except: pass 
            elif "lt" in ucp_lower and "ml" in umb_lower:
                try:
                    num_lt_str = ''.join(filter(lambda x: x.isdigit() or x == '.', ucp_lower.split('lt')[0].strip()))
                    num_lt = Decimal(num_lt_str) if num_lt_str else Decimal('1')
                    cantidad_por_presentacion_proveedor = num_lt * Decimal('1000')
                except: pass
    
    if cantidad_por_presentacion_proveedor <= 0:
        print(f"WARN_PRECIO: cantidad_por_presentacion_proveedor fue <= 0, usando 1.0 para Producto ID: {producto_id}")
        cantidad_por_presentacion_proveedor = Decimal('1.0')

    unidades_a_comprar = Decimal('0')
    if cantidad_necesaria_base > 0:
        unidades_a_comprar = (cantidad_necesaria_base / cantidad_por_presentacion_proveedor).quantize(Decimal('1'), rounding=ROUND_UP)

    costo_total_insumo = unidades_a_comprar * mejor_opcion_precio_proveedor_obj.precio_compra
    print(f"DEBUG_PRECIO: Producto ID: {producto_id}, Cant/Pres: {cantidad_por_presentacion_proveedor}, Uds a Comprar: {unidades_a_comprar}, Costo: {costo_total_insumo}")
    
    return proveedor_seleccionado_obj, mejor_opcion_precio_proveedor_obj, unidades_a_comprar, costo_total_insumo, unidad_compra_proveedor_display


@ordenes_compra_bp.route('/desde-cotizacion/<int:id_cotizacion>')
def generar_orden_compra_desde_cotizacion(id_cotizacion):
    db = SessionLocal()
    try:
        print(f"DEBUG_OC: Iniciando generación de OC para Cotización ID: {id_cotizacion}")
        cotizacion = db.query(Cotizacion).options(
            joinedload(Cotizacion.proyecto),
            selectinload(Cotizacion.items_cotizacion).selectinload(ItemCotizacion.componentes_seleccionados).selectinload(DetalleComponenteSeleccionado.opcion_componente_elegida).options(
                selectinload(OpcionComponenteServicio.producto_interno_ref)
            )
        ).get(id_cotizacion)

        if not cotizacion:
            flash("Cotización no encontrada.", "danger")
            print(f"DEBUG_OC: Cotización ID {id_cotizacion} no encontrada.")
            return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones'))
        
        print(f"DEBUG_OC: Cotización '{cotizacion.id_cotizacion}' cargada. Estado: {cotizacion.estado}")
        if cotizacion.estado != "Aceptada":
            flash(f"Advertencia: Esta cotización está en estado '{cotizacion.estado}'. Las órdenes de compra usualmente se generan para cotizaciones aceptadas.", "warning")
        
        insumos_compra_agregados = defaultdict(lambda: {
            'nombre_display': '', 'cantidad_total_base': Decimal('0.0'),
            'unidad_medida_base': '', 'es_producto_interno': False,
            'producto_obj': None, 'opcion_obj': None,
            'es_indivisible_final': False
        })
        print(f"DEBUG_OC: Cotización ID: {cotizacion.id_cotizacion}, Items en Cotización: {len(cotizacion.items_cotizacion)}")

        for item_cot in cotizacion.items_cotizacion:
            print(f"DEBUG_OC:   Procesando ItemCotizacion ID: {item_cot.id_item_cotizacion}, Nombre: '{item_cot.nombre_display_servicio}', Cantidad Servicio: {item_cot.cantidad_servicio}")
            print(f"DEBUG_OC:     Componentes Seleccionados para este Item: {len(item_cot.componentes_seleccionados)}")
            if not item_cot.componentes_seleccionados:
                continue
            for comp_sel in item_cot.componentes_seleccionados:
                print(f"DEBUG_OC:     Procesando DetalleComponenteSeleccionado ID: {comp_sel.id_detalle_seleccion}, ID Opcion FK: {comp_sel.id_opcion_componente}")
                opcion = comp_sel.opcion_componente_elegida 
                
                print(f"DEBUG_OC:       Opción Objeto (comp_sel.opcion_componente_elegida): {'Existe' if opcion else 'NO EXISTE'}")
                if opcion:
                    print(f"DEBUG_OC:         Opción ID desde objeto: {opcion.id_opcion_componente}, Nombre: '{opcion.nombre_display_cliente}'")
                    print(f"DEBUG_OC:         Producto Interno Ref en Opción: {'Existe' if opcion.producto_interno_ref else 'NO EXISTE'}")
                    if opcion.producto_interno_ref:
                        print(f"DEBUG_OC:           Producto Interno ID: {opcion.producto_interno_ref.id_producto}, Nombre: '{opcion.producto_interno_ref.nombre_producto}'")
                print(f"DEBUG_OC:       cantidad_final_producto_interno_calc en DetalleCompSel: {comp_sel.cantidad_final_producto_interno_calc} (Tipo: {type(comp_sel.cantidad_final_producto_interno_calc)})")

                if opcion and comp_sel.cantidad_final_producto_interno_calc is not None:
                    cantidad_necesaria_opcion_base = Decimal(comp_sel.cantidad_final_producto_interno_calc)
                    cantidad_total_para_item = cantidad_necesaria_opcion_base * item_cot.cantidad_servicio
                    
                    clave_agregacion, nombre_display_agregacion, unidad_base_agregacion, es_producto, producto_objeto_agregacion, opcion_objeto_agregacion, es_indivisible_temp = (None,)*7

                    if opcion.producto_interno_ref:
                        producto_insumo = opcion.producto_interno_ref
                        clave_agregacion = f"prod_{producto_insumo.id_producto}"
                        nombre_display_agregacion = producto_insumo.nombre_producto
                        unidad_base_agregacion = producto_insumo.unidad_medida_base
                        es_producto = True
                        producto_objeto_agregacion = producto_insumo
                        es_indivisible_temp = producto_insumo.es_indivisible
                        print(f"DEBUG_OC:         Insumo es PRODUCTO INTERNO: '{nombre_display_agregacion}'")
                    else: 
                        clave_agregacion = f"opcion_{opcion.id_opcion_componente}"
                        nombre_display_agregacion = opcion.nombre_display_cliente
                        unidad_base_agregacion = opcion.unidad_consumo_base
                        es_producto = False
                        opcion_objeto_agregacion = opcion
                        es_indivisible_temp = True if opcion.unidad_consumo_base and opcion.unidad_consumo_base.lower() in ['pieza', 'pza', 'unidad'] else False
                        print(f"DEBUG_OC:         Insumo es OPCIÓN DIRECTA: '{nombre_display_agregacion}'")

                    insumos_compra_agregados[clave_agregacion]['cantidad_total_base'] += cantidad_total_para_item
                    if not insumos_compra_agregados[clave_agregacion]['nombre_display']:
                        insumos_compra_agregados[clave_agregacion].update({
                            'nombre_display': nombre_display_agregacion,
                            'unidad_medida_base': unidad_base_agregacion,
                            'es_producto_interno': es_producto,
                            'es_indivisible_final': es_indivisible_temp,
                            'producto_obj': producto_objeto_agregacion,
                            'opcion_obj': opcion_objeto_agregacion
                        })
                    print(f"DEBUG_OC:         AGREGADO/ACTUALIZADO insumo '{clave_agregacion}', Cant Total Base ahora: {insumos_compra_agregados[clave_agregacion]['cantidad_total_base']}")
                else:
                    print(f"DEBUG_OC:       OMITIENDO DetalleCompSel ID: {comp_sel.id_detalle_seleccion}. Razón: opcion={opcion}, cantidad_calc={comp_sel.cantidad_final_producto_interno_calc}")
        
        print(f"DEBUG_OC: Insumos Agregados (antes de procesar para orden final): {dict(insumos_compra_agregados)}")
        
        orden_por_proveedor = defaultdict(list)
        costo_general_orden = Decimal('0.00')
        proveedor_no_definido_key = "Compra Directa / Por Definir"

        if not insumos_compra_agregados:
            print("DEBUG_OC: 'insumos_compra_agregados' está vacío. No se generarán ítems para la orden.")

        for clave, data_agregada in insumos_compra_agregados.items():
            print(f"DEBUG_OC:   Procesando para orden final, clave: {clave}, data: {data_agregada['nombre_display']}")
            cantidad_total_necesaria_base_agregada = data_agregada['cantidad_total_base']
            if data_agregada['es_indivisible_final']:
                cantidad_total_necesaria_base_agregada = cantidad_total_necesaria_base_agregada.quantize(Decimal('1'), rounding=ROUND_UP)

            item_para_orden = {
                'sku': 'DIRECTO', 
                'nombre_producto': data_agregada['nombre_display'],
                'cantidad_requerida_base': cantidad_total_necesaria_base_agregada,
                'unidad_medida_base': data_agregada['unidad_medida_base'],
                'presentacion_compra_proveedor': data_agregada['unidad_medida_base'], 
                'precio_por_presentacion': Decimal('0.00'),
                'cantidad_presentaciones_a_comprar': cantidad_total_necesaria_base_agregada if data_agregada['es_indivisible_final'] else Decimal('1'),
                'costo_total_insumo': Decimal('0.00'),
                'es_indivisible': data_agregada['es_indivisible_final'],
                'es_opcion_directa': not data_agregada['es_producto_interno']
            }
            proveedor_actual_nombre = proveedor_no_definido_key

            if data_agregada['es_producto_interno']:
                producto = data_agregada['producto_obj']
                item_para_orden['sku'] = producto.sku
                item_para_orden['es_indivisible'] = producto.es_indivisible 

                proveedor_obj, precio_prov_obj, uds_a_comprar, costo_insumo, unidad_compra_disp = seleccionar_mejor_precio_proveedor(db, producto.id_producto, cantidad_total_necesaria_base_agregada)
                
                if proveedor_obj and precio_prov_obj:
                    proveedor_actual_nombre = proveedor_obj.nombre_proveedor
                    item_para_orden['presentacion_compra_proveedor'] = unidad_compra_disp
                    item_para_orden['precio_por_presentacion'] = precio_prov_obj.precio_compra
                    item_para_orden['cantidad_presentaciones_a_comprar'] = uds_a_comprar
                    item_para_orden['costo_total_insumo'] = costo_insumo
                    costo_general_orden += costo_insumo
                else: 
                    proveedor_actual_nombre = "Proveedor no encontrado"
                    print(f"WARN_OC: No se encontró proveedor/precio para producto interno ID: {producto.id_producto}, Nombre: {producto.nombre_producto}")
            
            print(f"DEBUG_OC:     Añadiendo item '{item_para_orden['nombre_producto']}' a proveedor '{proveedor_actual_nombre}'")
            orden_por_proveedor[proveedor_actual_nombre].append(item_para_orden)
        
        orden_por_proveedor_final = {}
        for prov_nombre, items in orden_por_proveedor.items():
            orden_por_proveedor_final[prov_nombre] = sorted(items, key=lambda x: x['nombre_producto'])

        print(f"DEBUG_OC: 'orden_por_proveedor_final' (para plantilla): {orden_por_proveedor_final}")
        if not orden_por_proveedor_final:
             flash("No se calcularon insumos para esta cotización. Verifique la configuración de los servicios y opciones.", "info")
             print("DEBUG_OC: 'orden_por_proveedor_final' está vacío, se mostrará mensaje de 'No se calcularon insumos'.")


        return render_template('orden_compra_desde_cotizacion.html',
                               cotizacion=cotizacion,
                               proyecto=cotizacion.proyecto,
                               orden_por_proveedor=orden_por_proveedor_final, 
                               costo_total_general_orden=costo_general_orden,
                               fecha_generacion_oc=date.today(),
                               titulo_pagina=f"Orden de Compra para Cotización {cotizacion.id_cotizacion}")

    except Exception as e:
        flash(f"Error al generar la orden de compra: {str(e)}", "danger")
        import traceback
        traceback.print_exc()
        return redirect(url_for('cotizaciones_bp.vista_ver_cotizacion', id_cotizacion=id_cotizacion))
    finally:
        if db.is_active:
            db.close()
