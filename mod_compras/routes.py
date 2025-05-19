# /mod_compras/routes.py
from flask import render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Tuple # Importar Tuple para la anotación de tipo

from . import compras_bp
from database import SessionLocal
from models import Proveedor, EncabezadoCompra, DetalleCompra, Producto, Almacen, ExistenciaProducto, MovimientoInventario

# --- INICIO: Función auxiliar de conversión (si no está en un utils global) ---
def local_convertir_a_unidad_base(db: Session, id_producto: int, cantidad_presentacion_compra: Decimal, unidad_presentacion_compra: str) -> Tuple[Decimal, str]:
    producto_obj = db.query(Producto).get(id_producto)
    if not producto_obj:
        raise ValueError(f"Producto con ID {id_producto} no encontrado para conversión de unidades.")

    if producto_obj.unidad_medida_base and unidad_presentacion_compra.lower() == producto_obj.unidad_medida_base.lower():
        return cantidad_presentacion_compra, producto_obj.unidad_medida_base

    if producto_obj.presentacion_compra and producto_obj.cantidad_en_presentacion_compra and \
       unidad_presentacion_compra.lower() == producto_obj.presentacion_compra.lower():
        return cantidad_presentacion_compra * producto_obj.cantidad_en_presentacion_compra, producto_obj.unidad_medida_base
    
    if "kg" in unidad_presentacion_compra.lower() and producto_obj.unidad_medida_base.lower() == "g":
        try:
            factor_kg = Decimal(''.join(filter(lambda x: x.isdigit() or x == '.', unidad_presentacion_compra.split('kg')[0].strip())) or '1')
            return cantidad_presentacion_compra * factor_kg * Decimal('1000'), "g"
        except (InvalidOperation, IndexError):
            pass

    if "docena" in unidad_presentacion_compra.lower() and producto_obj.unidad_medida_base.lower() in ["pieza", "unidad", "pza"]:
        return cantidad_presentacion_compra * Decimal('12'), producto_obj.unidad_medida_base
    
    flash(f"Advertencia de conversión: No se pudo convertir '{unidad_presentacion_compra}' a '{producto_obj.unidad_medida_base}' para el producto '{producto_obj.nombre_producto}'. Se asume que la cantidad de compra ya está en unidad base.", "warning")
    return cantidad_presentacion_compra, producto_obj.unidad_medida_base
# --- FIN: Función auxiliar de conversión ---


@compras_bp.route('/registrar', methods=['GET', 'POST'])
def vista_registrar_compra():
    db = None  # Inicializar db a None
    try:
        db = SessionLocal() # Asignar la sesión dentro del try
        proveedores_activos = db.query(Proveedor).filter_by(activo=True).order_by(Proveedor.nombre_proveedor).all()
        almacen_principal_id = 1 
        almacen_destino_obj = db.query(Almacen).filter_by(id_almacen=almacen_principal_id, activo=True).first()
        
        if not almacen_destino_obj:
            almacen_existente = db.query(Almacen).filter(Almacen.nombre_almacen.ilike("Principal")).first()
            if not almacen_existente:
                almacen_destino_obj = Almacen(nombre_almacen="Principal", descripcion="Almacén principal por defecto")
                db.add(almacen_destino_obj)
                db.flush() 
                almacen_principal_id = almacen_destino_obj.id_almacen
                flash("Almacén 'Principal' creado por defecto.", "info")
            else:
                almacen_principal_id = almacen_existente.id_almacen
                # almacen_destino_obj = almacen_existente # Ya no es necesario reasignar aquí

            # Volver a consultar almacen_destino_obj después de posible creación/asignación
            almacen_destino_obj = db.query(Almacen).get(almacen_principal_id)
            if not almacen_destino_obj:
                 flash("No se encontró un almacén de destino activo. Por favor, crea uno primero.", "danger")
                 return redirect(url_for('inventario_bp.vista_gestionar_almacenes'))

        form_data_repopulate = {}

        if request.method == 'POST':
            form_data_repopulate = request.form.to_dict(flat=False)
            
            id_proveedor_form = request.form.get('id_proveedor')
            fecha_documento_form_str = request.form.get('fecha_documento')
            numero_documento_form = request.form.get('numero_documento')
            notas_generales_form = request.form.get('notas_generales')
            
            detalles_compra_form = []
            idx = 0
            while f'detalles[{idx}][id_producto]' in request.form:
                try:
                    cantidad_comprada_str = request.form[f'detalles[{idx}][cantidad_comprada]']
                    costo_unitario_compra_str = request.form[f'detalles[{idx}][costo_unitario_compra]']
                    unidad_compra_form = request.form[f'detalles[{idx}][unidad_compra]']

                    if not cantidad_comprada_str or not costo_unitario_compra_str or not unidad_compra_form:
                        flash(f"Cantidad, Costo Unitario y Unidad de Compra son obligatorios para el producto en la fila {idx+1}.", "warning")
                        idx += 1
                        continue

                    detalle_item = {
                        'id_producto': int(request.form[f'detalles[{idx}][id_producto]']),
                        'cantidad_comprada_presentacion': Decimal(cantidad_comprada_str),
                        'unidad_compra_presentacion': unidad_compra_form,
                        'precio_original_unitario': Decimal(request.form.get(f'detalles[{idx}][precio_original_unitario]', costo_unitario_compra_str)) if request.form.get(f'detalles[{idx}][precio_original_unitario]') else Decimal(costo_unitario_compra_str),
                        'monto_descuento_unitario': Decimal(request.form.get(f'detalles[{idx}][monto_descuento_unitario]', '0.00')) if request.form.get(f'detalles[{idx}][monto_descuento_unitario]') else Decimal('0.00'),
                        'costo_unitario_compra_presentacion': Decimal(costo_unitario_compra_str),
                        'disponibilidad_proveedor': request.form.get(f'detalles[{idx}][disponibilidad_proveedor]'),
                        'notas_item': request.form.get(f'detalles[{idx}][notas_item]')
                    }
                    detalle_item['costo_total_item_presentacion'] = detalle_item['cantidad_comprada_presentacion'] * detalle_item['costo_unitario_compra_presentacion']
                    detalles_compra_form.append(detalle_item)
                except (ValueError, TypeError, InvalidOperation) as e_parse:
                    flash(f"Error en los datos del producto en la fila {idx+1}: {e_parse}. Se omite este ítem.", "warning")
                idx += 1
            
            if not id_proveedor_form or not fecha_documento_form_str:
                flash("Proveedor y Fecha del Documento son obligatorios.", "danger")
            elif not detalles_compra_form:
                flash("Debe añadir al menos un producto a la compra.", "danger")
            else:
                # Mover el try-except para operaciones de BD aquí dentro del POST
                try:
                    fecha_documento_obj = date.fromisoformat(fecha_documento_form_str)
                    monto_total_calculado_presentacion = sum(d['costo_total_item_presentacion'] for d in detalles_compra_form)

                    nuevo_encabezado = EncabezadoCompra(
                        id_proveedor=int(id_proveedor_form),
                        fecha_documento=fecha_documento_obj,
                        numero_documento=numero_documento_form,
                        monto_total_documento=monto_total_calculado_presentacion,
                        notas_generales=notas_generales_form
                    )
                    db.add(nuevo_encabezado)
                    db.flush() 

                    for det_data in detalles_compra_form:
                        nuevo_detalle_compra = DetalleCompra(
                            id_encabezado_compra=nuevo_encabezado.id_encabezado_compra,
                            id_producto=det_data['id_producto'],
                            cantidad_comprada=det_data['cantidad_comprada_presentacion'],
                            unidad_compra=det_data['unidad_compra_presentacion'],
                            precio_original_unitario=det_data['precio_original_unitario'],
                            monto_descuento_unitario=det_data['monto_descuento_unitario'],
                            costo_unitario_compra=det_data['costo_unitario_compra_presentacion'],
                            costo_total_item=det_data['costo_total_item_presentacion'],
                            disponibilidad_proveedor=det_data['disponibilidad_proveedor'],
                            notas_item=det_data['notas_item']
                        )
                        db.add(nuevo_detalle_compra)
                        db.flush()

                        try:
                            cantidad_convertida_base, unidad_base_producto = local_convertir_a_unidad_base(
                                db,
                                det_data['id_producto'],
                                det_data['cantidad_comprada_presentacion'],
                                det_data['unidad_compra_presentacion']
                            )
                            
                            costo_unitario_base = None
                            if cantidad_convertida_base > 0 :
                                 costo_unitario_base = det_data['costo_total_item_presentacion'] / cantidad_convertida_base
                            elif det_data['costo_total_item_presentacion'] > 0:
                                flash(f"Advertencia: Cantidad convertida a base es 0 para producto ID {det_data['id_producto']} pero tiene costo. No se registrará costo unitario en movimiento.", "warning")

                            movimiento_entrada = MovimientoInventario(
                                id_producto=det_data['id_producto'],
                                id_almacen_destino=almacen_principal_id,
                                tipo_movimiento="ENTRADA_COMPRA",
                                cantidad=cantidad_convertida_base,
                                fecha_movimiento=datetime.now(),
                                id_documento_referencia=nuevo_detalle_compra.id_detalle_compra,
                                tipo_documento_referencia="DETALLE_COMPRA",
                                costo_unitario_en_movimiento=costo_unitario_base,
                                notas=f"Compra Fact./Nota: {nuevo_encabezado.numero_documento or 'N/A'}"
                            )
                            db.add(movimiento_entrada)

                            existencia = db.query(ExistenciaProducto).filter_by(
                                id_producto=det_data['id_producto'],
                                id_almacen=almacen_principal_id
                            ).first()

                            if not existencia:
                                existencia = ExistenciaProducto(
                                    id_producto=det_data['id_producto'],
                                    id_almacen=almacen_principal_id,
                                    cantidad_disponible=Decimal('0.0')
                                )
                                db.add(existencia)
                            
                            existencia.cantidad_disponible += cantidad_convertida_base
                            existencia.ultima_actualizacion = datetime.now()
                        
                        except ValueError as ve_conv:
                            flash(f"Error al convertir unidades para el producto en la compra (ID: {det_data['id_producto']}): {str(ve_conv)}. El movimiento de inventario podría no ser preciso.", "danger")
                    
                    db.commit()
                    flash(f"Compra registrada (ID Enc: {nuevo_encabezado.id_encabezado_compra}) y stock actualizado.", "success")
                    return redirect(url_for('compras_bp.vista_listar_facturas_compra'))
                
                except ValueError:
                     if db.is_active: db.rollback()
                     flash("Formato de fecha inválido en la compra.", "danger")
                except InvalidOperation:
                    if db.is_active: db.rollback()
                    flash("Formato numérico inválido en alguno de los montos de la compra.", "danger")
                except Exception as e: # Captura más genérica para errores de BD en el commit
                    if db.is_active: db.rollback()
                    flash(f"Error al registrar la compra: {str(e)}", "danger")
                    import traceback
                    traceback.print_exc()
            
            # Si hubo errores de validación o de BD, repopular el formulario
            form_data_repopulate_final = {
                'id_proveedor': id_proveedor_form, # Usar las variables del form
                'fecha_documento': fecha_documento_form_str,
                'numero_documento': numero_documento_form,
                'notas_generales': notas_generales_form,
                'detalles': detalles_compra_form # Usar los detalles parseados
            }
            return render_template('registrar_compra.html',
                                   proveedores=proveedores_activos,
                                   fecha_hoy=date.today().isoformat(),
                                   form_data=form_data_repopulate_final,
                                   titulo_pagina="Registrar Nueva Compra")

        # Método GET
        return render_template('registrar_compra.html',
                               proveedores=proveedores_activos,
                               fecha_hoy=date.today().isoformat(),
                               form_data=form_data_repopulate, # Estará vacío en el GET inicial
                               titulo_pagina="Registrar Nueva Compra")
    finally:
        if db and db.is_active: # Comprobar que db no sea None antes de acceder a is_active
            db.close()


@compras_bp.route('/historial', methods=['GET'])
def vista_historial_compras():
    db = None
    try:
        db = SessionLocal()
        detalles_de_compras = db.query(DetalleCompra).join(DetalleCompra.encabezado)\
            .options(
                joinedload(DetalleCompra.producto),
                joinedload(DetalleCompra.encabezado).joinedload(EncabezadoCompra.proveedor)
            )\
            .order_by(desc(EncabezadoCompra.fecha_documento), desc(DetalleCompra.id_detalle_compra))\
            .all()

        return render_template('historial_compras.html',
                               compras=detalles_de_compras,
                               titulo_pagina="Historial de Compras por Producto")
    except Exception as e:
        flash(f"Error al cargar el historial de compras: {str(e)}", "danger")
        return render_template('historial_compras.html', compras=[], titulo_pagina="Historial de Compras por Producto")
    finally:
        if db and db.is_active:
            db.close()


@compras_bp.route('/facturas', methods=['GET'])
def vista_listar_facturas_compra():
    db = None
    try:
        db = SessionLocal()
        encabezados_compra = db.query(EncabezadoCompra).options(
            joinedload(EncabezadoCompra.proveedor)
        ).order_by(desc(EncabezadoCompra.fecha_documento), desc(EncabezadoCompra.id_encabezado_compra)).all()

        return render_template('listar_facturas_compra.html',
                               encabezados=encabezados_compra,
                               titulo_pagina="Listado de Facturas de Compra")
    except Exception as e:
        flash(f"Error al cargar las facturas de compra: {str(e)}", "danger")
        return render_template('listar_facturas_compra.html', encabezados=[], titulo_pagina="Listado de Facturas de Compra")
    finally:
        if db and db.is_active:
            db.close()
