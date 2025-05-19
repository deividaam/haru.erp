# /mod_ordenes_compra/routes.py
from flask import render_template, request, redirect, url_for, flash
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, func as sqlfunc
from decimal import Decimal, ROUND_UP
import math
from collections import defaultdict
from datetime import date, datetime # Asegurar datetime

from . import ordenes_compra_bp
from database import SessionLocal
from models import (
    Cotizacion, ItemCotizacion, DetalleComponenteSeleccionado,
    OpcionComponenteServicio, Producto, Proveedor, PrecioProveedor,
    # --- NUEVOS MODELOS DE INVENTARIO ---
    Almacen, ExistenciaProducto, MovimientoInventario
    # --- FIN NUEVOS MODELOS ---
)

# (Función seleccionar_mejor_precio_proveedor se mantiene igual que en tu archivo original)
def seleccionar_mejor_precio_proveedor(db_session: Session, producto_id: int, cantidad_necesaria_base: Decimal):
    # ... (código de tu función original)
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
        # Usar math.ceil para redondear hacia arriba al entero más cercano
        unidades_a_comprar = Decimal(math.ceil(cantidad_necesaria_base / cantidad_por_presentacion_proveedor))


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
                selectinload(OpcionComponenteServicio.producto_interno_ref) # Cargar el producto interno
            )
        ).get(id_cotizacion)

        if not cotizacion:
            flash("Cotización no encontrada.", "danger")
            return redirect(url_for('cotizaciones_bp.vista_listar_cotizaciones'))
        
        if cotizacion.estado != "Aceptada":
            flash(f"Advertencia: Esta cotización está en estado '{cotizacion.estado}'. Las órdenes de compra y reservas de inventario usualmente se gestionan para cotizaciones aceptadas.", "warning")
        
        insumos_compra_agregados = defaultdict(lambda: {
            'nombre_display': '', 'cantidad_total_base': Decimal('0.0'),
            'unidad_medida_base': '', 'es_producto_interno': False,
            'producto_obj': None, 'opcion_obj': None,
            'es_indivisible_final': False,
            'id_almacen_principal': 1 # Asumir almacén principal ID 1, ajustar si es necesario
        })
        
        almacen_principal_id_oc = 1 # ID del almacén principal para las existencias
        almacen_obj_oc = db.query(Almacen).get(almacen_principal_id_oc)
        if not almacen_obj_oc:
            # Crear almacén principal si no existe (solo para este ejemplo)
            almacen_existente_oc = db.query(Almacen).filter(Almacen.nombre_almacen.ilike("Principal")).first()
            if not almacen_existente_oc:
                almacen_obj_oc = Almacen(nombre_almacen="Principal", descripcion="Almacén principal por defecto")
                db.add(almacen_obj_oc)
                db.flush()
                almacen_principal_id_oc = almacen_obj_oc.id_almacen
            else:
                almacen_principal_id_oc = almacen_existente_oc.id_almacen

        # --- INICIO: Lógica de Reserva de Inventario ---
        if cotizacion.estado == "Aceptada": # Solo reservar si la cotización está aceptada
            for item_cot in cotizacion.items_cotizacion:
                for comp_sel in item_cot.componentes_seleccionados:
                    if comp_sel.opcion_componente_elegida and \
                       comp_sel.opcion_componente_elegida.producto_interno_ref and \
                       comp_sel.cantidad_final_producto_interno_calc is not None:
                        
                        producto_a_reservar = comp_sel.opcion_componente_elegida.producto_interno_ref
                        cantidad_a_reservar_base = Decimal(comp_sel.cantidad_final_producto_interno_calc) * item_cot.cantidad_servicio

                        existencia = db.query(ExistenciaProducto).filter_by(
                            id_producto=producto_a_reservar.id_producto,
                            id_almacen=almacen_principal_id_oc # Usar el ID del almacén
                        ).first()

                        if not existencia:
                            existencia = ExistenciaProducto(
                                id_producto=producto_a_reservar.id_producto,
                                id_almacen=almacen_principal_id_oc,
                                cantidad_disponible=Decimal('0.0'),
                                cantidad_reservada=Decimal('0.0')
                            )
                            db.add(existencia)
                        
                        existencia.cantidad_reservada += cantidad_a_reservar_base
                        existencia.ultima_actualizacion = datetime.now()
                        
                        # (Opcional) Crear un movimiento de reserva si se desea un historial más granular
                        # movimiento_reserva = MovimientoInventario(
                        #     id_producto=producto_a_reservar.id_producto,
                        #     id_almacen_origen=almacen_principal_id_oc, 
                        #     tipo_movimiento="RESERVA_EVENTO",
                        #     cantidad=cantidad_a_reservar_base,
                        #     id_documento_referencia=cotizacion.id_cotizacion,
                        #     tipo_documento_referencia="COTIZACION_ACEPTADA",
                        #     notas=f"Reserva para Cot. {cotizacion.id_cotizacion} V{cotizacion.version}"
                        # )
                        # db.add(movimiento_reserva)
            # db.commit() # Commit de las reservas al final del bucle o aquí si es por cotización
            flash(f"Inventario reservado para la cotización {cotizacion.id_cotizacion} (si aplica).", "info")
        # --- FIN: Lógica de Reserva de Inventario ---


        # ... (resto de tu lógica para calcular insumos_compra_agregados y orden_por_proveedor) ...
        # Esta parte se mantiene igual que tu original para la generación de la OC visual.
        for item_cot in cotizacion.items_cotizacion:
            if not item_cot.componentes_seleccionados:
                continue
            for comp_sel in item_cot.componentes_seleccionados:
                opcion = comp_sel.opcion_componente_elegida
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
                    else: 
                        clave_agregacion = f"opcion_{opcion.id_opcion_componente}"
                        nombre_display_agregacion = opcion.nombre_display_cliente
                        unidad_base_agregacion = opcion.unidad_consumo_base
                        es_producto = False
                        opcion_objeto_agregacion = opcion
                        es_indivisible_temp = True if opcion.unidad_consumo_base and opcion.unidad_consumo_base.lower() in ['pieza', 'pza', 'unidad'] else False

                    insumos_compra_agregados[clave_agregacion]['cantidad_total_base'] += cantidad_total_para_item
                    if not insumos_compra_agregados[clave_agregacion]['nombre_display']:
                        insumos_compra_agregados[clave_agregacion].update({
                            'nombre_display': nombre_display_agregacion,
                            'unidad_medida_base': unidad_base_agregacion,
                            'es_producto_interno': es_producto,
                            'es_indivisible_final': es_indivisible_temp,
                            'producto_obj': producto_objeto_agregacion,
                            'opcion_obj': opcion_objeto_agregacion,
                            'id_almacen_principal': almacen_principal_id_oc
                        })
        
        orden_por_proveedor = defaultdict(list)
        costo_general_orden = Decimal('0.00')
        proveedor_no_definido_key = "Compra Directa / Por Definir"

        for clave, data_agregada in insumos_compra_agregados.items():
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
            
            orden_por_proveedor[proveedor_actual_nombre].append(item_para_orden)
        
        orden_por_proveedor_final = {prov_nombre: sorted(items, key=lambda x: x['nombre_producto']) for prov_nombre, items in orden_por_proveedor.items()}
        
        # Commit final después de todas las operaciones de reserva
        db.commit()

        return render_template('orden_compra_desde_cotizacion.html',
                               cotizacion=cotizacion,
                               proyecto=cotizacion.proyecto,
                               orden_por_proveedor=orden_por_proveedor_final, 
                               costo_total_general_orden=costo_general_orden,
                               fecha_generacion_oc=date.today(),
                               titulo_pagina=f"Orden de Compra para Cotización {cotizacion.id_cotizacion}")

    except Exception as e:
        if db.is_active: db.rollback() # Rollback si algo falla
        flash(f"Error al generar la orden de compra o reservar inventario: {str(e)}", "danger")
        import traceback
        traceback.print_exc()
        return redirect(url_for('cotizaciones_bp.vista_ver_cotizacion', id_cotizacion=id_cotizacion))
    finally:
        if db.is_active:
            db.close()
