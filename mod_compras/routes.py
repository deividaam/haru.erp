# /mod_compras/routes.py
from flask import render_template, request, redirect, url_for, flash, jsonify # session no se usa aquí directamente
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from decimal import Decimal
from datetime import date

from . import compras_bp  # Importar el blueprint
from database import SessionLocal
from models import Proveedor, EncabezadoCompra, DetalleCompra, Producto
# Asegúrate de que todos los modelos necesarios estén importados.

# --- RUTAS PARA COMPRAS ---
# El prefijo '/compras' ya está definido en el Blueprint.

@compras_bp.route('/registrar', methods=['GET', 'POST'])
def vista_registrar_compra():
    db = SessionLocal()
    proveedores_activos = db.query(Proveedor).filter_by(activo=True).order_by(Proveedor.nombre_proveedor).all()
    form_data_repopulate = {} # Para repopular en caso de error o al inicio

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
                # Validar que los campos numéricos no estén vacíos antes de convertir
                cantidad_comprada_str = request.form[f'detalles[{idx}][cantidad_comprada]']
                costo_unitario_compra_str = request.form[f'detalles[{idx}][costo_unitario_compra]']

                if not cantidad_comprada_str or not costo_unitario_compra_str:
                    flash(f"Cantidad y Costo Unitario son obligatorios para el producto en la fila {idx+1}.", "warning")
                    idx += 1
                    continue # Saltar este ítem si faltan datos cruciales

                detalle_item = {
                    'id_producto': int(request.form[f'detalles[{idx}][id_producto]']),
                    'cantidad_comprada': Decimal(cantidad_comprada_str),
                    'unidad_compra': request.form[f'detalles[{idx}][unidad_compra]'],
                    'precio_original_unitario': Decimal(request.form.get(f'detalles[{idx}][precio_original_unitario]', '0.00')) if request.form.get(f'detalles[{idx}][precio_original_unitario]') else None,
                    'monto_descuento_unitario': Decimal(request.form.get(f'detalles[{idx}][monto_descuento_unitario]', '0.00')) if request.form.get(f'detalles[{idx}][monto_descuento_unitario]') else Decimal('0.00'),
                    'costo_unitario_compra': Decimal(costo_unitario_compra_str),
                    'disponibilidad_proveedor': request.form.get(f'detalles[{idx}][disponibilidad_proveedor]'),
                    'notas_item': request.form.get(f'detalles[{idx}][notas_item]')
                }
                detalle_item['costo_total_item'] = detalle_item['cantidad_comprada'] * detalle_item['costo_unitario_compra']
                detalles_compra_form.append(detalle_item)
            except (ValueError, TypeError) as e_parse:
                flash(f"Error en los datos del producto en la fila {idx+1}: {e_parse}. Se omite este ítem.", "warning")
            idx += 1
        
        if not id_proveedor_form or not fecha_documento_form_str:
            flash("Proveedor y Fecha del Documento son obligatorios.", "danger")
        elif not detalles_compra_form:
            flash("Debe añadir al menos un producto a la compra.", "danger")
        else:
            try:
                fecha_documento_obj = date.fromisoformat(fecha_documento_form_str)
                monto_total_calculado = sum(d['costo_total_item'] for d in detalles_compra_form)

                nuevo_encabezado = EncabezadoCompra(
                    id_proveedor=int(id_proveedor_form),
                    fecha_documento=fecha_documento_obj,
                    numero_documento=numero_documento_form,
                    monto_total_documento=monto_total_calculado,
                    notas_generales=notas_generales_form
                )
                db.add(nuevo_encabezado)
                db.flush() 

                for det_data in detalles_compra_form:
                    nuevo_detalle = DetalleCompra(
                        id_encabezado_compra=nuevo_encabezado.id_encabezado_compra,
                        **det_data
                    )
                    db.add(nuevo_detalle)
                
                db.commit()
                flash(f"Compra registrada exitosamente (Factura/Nota ID: {nuevo_encabezado.id_encabezado_compra}).", "success")
                if db.is_active: db.close()
                return redirect(url_for('compras_bp.vista_listar_facturas_compra'))
            except ValueError:
                 if db.is_active: db.rollback()
                 flash("Formato de fecha o número inválido en la compra.", "danger")
            except Exception as e:
                if db.is_active: db.rollback()
                flash(f"Error al registrar la compra: {str(e)}", "danger")
        
        # Repopular detalles para la plantilla en caso de error
        detalles_repop = []
        if 'detalles[0][id_producto]' in form_data_repopulate: # Chequear si hay al menos un detalle
            # Esta lógica de repopulación puede ser compleja si los nombres de producto no se envían
            # Asumimos que el JS en el frontend maneja la visualización del nombre y sku.
            # Aquí solo repopulamos los IDs y valores numéricos/texto.
            idx_repop = 0
            while form_data_repopulate.get(f'detalles[{idx_repop}][id_producto]'):
                try:
                    det_item_repop = {
                        'id_producto': form_data_repopulate[f'detalles[{idx_repop}][id_producto]'][0],
                        'cantidad_comprada': form_data_repopulate[f'detalles[{idx_repop}][cantidad_comprada]'][0],
                        'unidad_compra': form_data_repopulate[f'detalles[{idx_repop}][unidad_compra]'][0],
                        'precio_original_unitario': form_data_repopulate.get(f'detalles[{idx_repop}][precio_original_unitario]', ['0.00'])[0],
                        'monto_descuento_unitario': form_data_repopulate.get(f'detalles[{idx_repop}][monto_descuento_unitario]', ['0.00'])[0],
                        'costo_unitario_compra': form_data_repopulate[f'detalles[{idx_repop}][costo_unitario_compra]'][0],
                        'disponibilidad_proveedor': form_data_repopulate.get(f'detalles[{idx_repop}][disponibilidad_proveedor]', ['Media'])[0],
                        'notas_item': form_data_repopulate.get(f'detalles[{idx_repop}][notas_item]', [''])[0],
                        # Para mostrar en tabla, necesitarías obtener nombre y sku basados en id_producto
                        'nombre_producto_display': f"Producto ID {form_data_repopulate[f'detalles[{idx_repop}][id_producto]'][0]}", # Placeholder
                        'sku_producto_display': '' # Placeholder
                    }
                    detalles_repop.append(det_item_repop)
                except (KeyError, IndexError): # Manejar el caso donde no todos los campos esperados están presentes
                    pass 
                idx_repop += 1


        form_data_repopulate_final = {
            'id_proveedor': id_proveedor_form,
            'fecha_documento': fecha_documento_form_str,
            'numero_documento': numero_documento_form,
            'notas_generales': notas_generales_form,
            'detalles': detalles_repop # Pasar los detalles procesados
        }
        if db.is_active: db.close()
        return render_template('registrar_compra.html',
                               proveedores=proveedores_activos,
                               fecha_hoy=date.today().isoformat(),
                               form_data=form_data_repopulate_final,
                               titulo_pagina="Registrar Nueva Compra")

    # Método GET
    if db.is_active: db.close()
    return render_template('registrar_compra.html',
                           proveedores=proveedores_activos,
                           fecha_hoy=date.today().isoformat(),
                           form_data=form_data_repopulate,
                           titulo_pagina="Registrar Nueva Compra")


@compras_bp.route('/historial', methods=['GET'])
def vista_historial_compras():
    db = SessionLocal()
    try:
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
        if db.is_active:
            db.close()

@compras_bp.route('/facturas', methods=['GET'])
def vista_listar_facturas_compra():
    db = SessionLocal()
    try:
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
        if db.is_active:
            db.close()
