# /mod_inventario/routes.py
from flask import render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, or_
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Tuple # Importar Tuple para la anotación de tipo

from . import inventario_bp
from database import SessionLocal
from models import Producto, Almacen, ExistenciaProducto, MovimientoInventario
# Importar otros modelos si son necesarios para la lógica de conversión o referencias

# CORRECCIÓN: Cambiada la anotación de tipo de retorno
def local_convertir_a_unidad_base(db: Session, id_producto: int, cantidad_presentacion_compra: Decimal, unidad_presentacion_compra: str) -> Tuple[Decimal, str]:
    """
    Convierte una cantidad dada en una presentación de compra a la unidad base del producto.
    Retorna la cantidad convertida en unidad base y la unidad base.
    Esta es una función simplificada. Necesitarás una lógica más robusta si las conversiones son complejas.
    """
    producto_obj = db.query(Producto).get(id_producto)
    if not producto_obj:
        raise ValueError(f"Producto con ID {id_producto} no encontrado para conversión de unidades.")

    # Caso 1: La unidad de compra es la misma que la unidad base del producto.
    if producto_obj.unidad_medida_base and unidad_presentacion_compra.lower() == producto_obj.unidad_medida_base.lower():
        return cantidad_presentacion_compra, producto_obj.unidad_medida_base

    # Caso 2: La unidad de compra coincide con Producto.presentacion_compra y existe cantidad_en_presentacion_compra
    if producto_obj.presentacion_compra and producto_obj.cantidad_en_presentacion_compra and \
       unidad_presentacion_compra.lower() == producto_obj.presentacion_compra.lower():
        return cantidad_presentacion_compra * producto_obj.cantidad_en_presentacion_compra, producto_obj.unidad_medida_base
    
    # Lógica de conversión más específica (ejemplos básicos)
    # Deberás expandir esto considerablemente o usar una librería de conversión de unidades.
    # Ejemplo: si compras "Bolsa 1kg" y tu unidad base es "g"
    if "kg" in unidad_presentacion_compra.lower() and producto_obj.unidad_medida_base.lower() == "g":
        try:
            # Extraer el número de kg de la unidad_presentacion_compra, ej "Bolsa 1kg" -> 1, "Paquete 0.5kg" -> 0.5
            factor_kg = Decimal(''.join(filter(lambda x: x.isdigit() or x == '.', unidad_presentacion_compra.split('kg')[0].strip())) or '1')
            return cantidad_presentacion_compra * factor_kg * Decimal('1000'), "g"
        except (InvalidOperation, IndexError):
            # Si falla la extracción del factor, podría intentar una conversión genérica o fallar.
            pass # Continuar con otras reglas si esta falla

    if "docena" in unidad_presentacion_compra.lower() and producto_obj.unidad_medida_base.lower() in ["pieza", "unidad", "pza"]:
        return cantidad_presentacion_compra * Decimal('12'), producto_obj.unidad_medida_base
    
    # Fallback: Si no hay regla de conversión clara, se asume que la cantidad ya está en unidad base
    # Esto es riesgoso y deberías tener una validación más estricta o un sistema de factores de conversión.
    flash(f"Advertencia de conversión: No se pudo convertir '{unidad_presentacion_compra}' a '{producto_obj.unidad_medida_base}' para el producto '{producto_obj.nombre_producto}'. Se asume que la cantidad de compra ya está en unidad base.", "warning")
    return cantidad_presentacion_compra, producto_obj.unidad_medida_base


@inventario_bp.route('/existencias')
def vista_listar_existencias():
    db = SessionLocal()
    try:
        search_term = request.args.get('q', '').strip()
        id_almacen_filter = request.args.get('id_almacen', type=int)

        query = db.query(ExistenciaProducto).options(
            joinedload(ExistenciaProducto.producto).joinedload(Producto.categoria_principal_producto),
            joinedload(ExistenciaProducto.almacen)
        )

        if search_term:
            query = query.join(Producto).filter(
                or_(
                    Producto.nombre_producto.ilike(f"%{search_term}%"),
                    Producto.sku.ilike(f"%{search_term}%")
                )
            )
        
        if id_almacen_filter:
            query = query.filter(ExistenciaProducto.id_almacen == id_almacen_filter)

        existencias = query.order_by(desc(ExistenciaProducto.ultima_actualizacion)).all()
        almacenes = db.query(Almacen).filter_by(activo=True).order_by(Almacen.nombre_almacen).all()
        
        return render_template('listar_existencias.html',
                               existencias=existencias,
                               almacenes=almacenes,
                               current_filters={'q': search_term, 'id_almacen': id_almacen_filter},
                               titulo_pagina="Existencias de Productos")
    except Exception as e:
        flash(f"Error al cargar existencias: {str(e)}", "danger")
        return render_template('listar_existencias.html', existencias=[], almacenes=[], current_filters={}, titulo_pagina="Existencias de Productos")
    finally:
        db.close()

@inventario_bp.route('/movimientos')
def vista_historial_movimientos():
    db = SessionLocal()
    try:
        id_producto_filter = request.args.get('id_producto', type=int)
        id_almacen_filter = request.args.get('id_almacen', type=int)
        tipo_movimiento_filter = request.args.get('tipo_movimiento', '').strip()
        fecha_desde_str = request.args.get('fecha_desde', '')
        fecha_hasta_str = request.args.get('fecha_hasta', '')

        query = db.query(MovimientoInventario).options(
            joinedload(MovimientoInventario.producto),
            joinedload(MovimientoInventario.almacen_origen_rel),
            joinedload(MovimientoInventario.almacen_destino_rel)
        )

        if id_producto_filter:
            query = query.filter(MovimientoInventario.id_producto == id_producto_filter)
        if id_almacen_filter:
            query = query.filter(or_(
                MovimientoInventario.id_almacen_origen == id_almacen_filter,
                MovimientoInventario.id_almacen_destino == id_almacen_filter
            ))
        if tipo_movimiento_filter:
            query = query.filter(MovimientoInventario.tipo_movimiento == tipo_movimiento_filter)
        
        if fecha_desde_str:
            try:
                fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d')
                query = query.filter(MovimientoInventario.fecha_movimiento >= fecha_desde)
            except ValueError:
                flash("Formato de 'Fecha Desde' inválido. Usar AAAA-MM-DD.", "warning")
        if fecha_hasta_str:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query = query.filter(MovimientoInventario.fecha_movimiento <= fecha_hasta)
            except ValueError:
                flash("Formato de 'Fecha Hasta' inválido. Usar AAAA-MM-DD.", "warning")

        movimientos = query.order_by(desc(MovimientoInventario.fecha_movimiento)).all()
        
        productos_para_filtro = db.query(Producto.id_producto, Producto.nombre_producto, Producto.sku).filter_by(activo=True).order_by(Producto.nombre_producto).all()
        almacenes_para_filtro = db.query(Almacen.id_almacen, Almacen.nombre_almacen).filter_by(activo=True).order_by(Almacen.nombre_almacen).all()
        tipos_movimiento_distintos = [m[0] for m in db.query(MovimientoInventario.tipo_movimiento).distinct().order_by(MovimientoInventario.tipo_movimiento).all()]

        current_filters = {
            'id_producto': id_producto_filter,
            'id_almacen': id_almacen_filter,
            'tipo_movimiento': tipo_movimiento_filter,
            'fecha_desde': fecha_desde_str,
            'fecha_hasta': fecha_hasta_str,
        }
        return render_template('historial_movimientos.html',
                               movimientos=movimientos,
                               productos_filtro=productos_para_filtro,
                               almacenes_filtro=almacenes_para_filtro,
                               tipos_movimiento_filtro=tipos_movimiento_distintos,
                               current_filters=current_filters,
                               titulo_pagina="Historial de Movimientos de Inventario")
    except Exception as e:
        flash(f"Error al cargar historial de movimientos: {str(e)}", "danger")
        return render_template('historial_movimientos.html', movimientos=[], productos_filtro=[], almacenes_filtro=[], tipos_movimiento_filtro=[], current_filters={}, titulo_pagina="Historial de Movimientos de Inventario")
    finally:
        db.close()

@inventario_bp.route('/ajuste/nuevo', methods=['GET', 'POST'])
def vista_crear_ajuste_inventario():
    db = SessionLocal()
    try:
        almacenes = db.query(Almacen).filter_by(activo=True).order_by(Almacen.nombre_almacen).all()
        # productos ya no se carga aquí, se usa la API para búsqueda dinámica
        # productos = db.query(Producto.id_producto, Producto.nombre_producto, Producto.sku).filter_by(activo=True).order_by(Producto.nombre_producto).all()

        if request.method == 'POST':
            id_producto_form = request.form.get('id_producto', type=int)
            id_almacen_form = request.form.get('id_almacen_destino', type=int)
            tipo_ajuste = request.form.get('tipo_ajuste')
            cantidad_str = request.form.get('cantidad')
            notas_form = request.form.get('notas')

            if not all([id_producto_form, id_almacen_form, tipo_ajuste, cantidad_str]):
                flash("Producto, Almacén, Tipo de Ajuste y Cantidad son obligatorios.", "danger")
            else:
                try:
                    cantidad_ajuste = Decimal(cantidad_str)
                    if cantidad_ajuste <= 0:
                        flash("La cantidad del ajuste debe ser mayor a cero.", "danger")
                    else:
                        producto_obj = db.query(Producto).get(id_producto_form)
                        almacen_obj = db.query(Almacen).get(id_almacen_form)

                        if not producto_obj or not almacen_obj:
                            flash("Producto o Almacén no válido.", "danger")
                        else:
                            nuevo_movimiento = MovimientoInventario(
                                id_producto=id_producto_form,
                                id_almacen_destino=id_almacen_form if "POSITIVO" in tipo_ajuste.upper() else None,
                                id_almacen_origen=id_almacen_form if "NEGATIVO" in tipo_ajuste.upper() else None,
                                tipo_movimiento=tipo_ajuste,
                                cantidad=cantidad_ajuste,
                                fecha_movimiento=datetime.now(),
                                tipo_documento_referencia="AJUSTE_MANUAL",
                                notas=notas_form,
                            )
                            db.add(nuevo_movimiento)

                            existencia = db.query(ExistenciaProducto).filter_by(
                                id_producto=id_producto_form,
                                id_almacen=id_almacen_form
                            ).first()

                            if not existencia:
                                existencia = ExistenciaProducto(
                                    id_producto=id_producto_form,
                                    id_almacen=id_almacen_form,
                                    cantidad_disponible=Decimal('0.0')
                                )
                                db.add(existencia)
                            
                            if "POSITIVO" in tipo_ajuste.upper():
                                existencia.cantidad_disponible += cantidad_ajuste
                            elif "NEGATIVO" in tipo_ajuste.upper():
                                existencia.cantidad_disponible -= cantidad_ajuste
                            
                            db.commit()
                            flash(f"Ajuste de inventario para '{producto_obj.nombre_producto}' registrado exitosamente.", "success")
                            return redirect(url_for('inventario_bp.vista_listar_existencias'))
                
                except InvalidOperation:
                    flash("Cantidad debe ser un número válido.", "danger")
                except ValueError as ve:
                     flash(str(ve), "danger")

        return render_template('form_ajuste_inventario.html',
                               almacenes=almacenes,
                               # productos=productos, # Ya no se pasa la lista completa
                               form_data=request.form if request.method == 'POST' else {},
                               titulo_pagina="Nuevo Ajuste Manual de Inventario")
    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error al procesar ajuste de inventario: {str(e)}", "danger")
        return redirect(url_for('inventario_bp.vista_listar_existencias'))
    finally:
        db.close()

@inventario_bp.route('/almacenes', methods=['GET', 'POST'])
def vista_gestionar_almacenes():
    db = SessionLocal()
    try:
        if request.method == 'POST':
            nombre_almacen = request.form.get('nombre_almacen', '').strip()
            descripcion_almacen = request.form.get('descripcion', '').strip()
            if not nombre_almacen:
                flash("El nombre del almacén es obligatorio.", "danger")
            else:
                existente = db.query(Almacen).filter(Almacen.nombre_almacen.ilike(nombre_almacen)).first()
                if existente:
                    flash(f"Ya existe un almacén con el nombre '{nombre_almacen}'.", "warning")
                else:
                    nuevo_almacen = Almacen(nombre_almacen=nombre_almacen, descripcion=descripcion_almacen, activo=True)
                    db.add(nuevo_almacen)
                    db.commit()
                    flash(f"Almacén '{nombre_almacen}' creado exitosamente.", "success")
                    return redirect(url_for('inventario_bp.vista_gestionar_almacenes'))
        
        almacenes = db.query(Almacen).order_by(Almacen.nombre_almacen).all()
        return render_template('gestionar_almacenes.html',
                               almacenes=almacenes,
                               form_data=request.form if request.method == 'POST' else {},
                               titulo_pagina="Gestionar Almacenes")
    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error al gestionar almacenes: {str(e)}", "danger")
        return render_template('gestionar_almacenes.html', almacenes=[], form_data={}, titulo_pagina="Gestionar Almacenes")
    finally:
        db.close()

@inventario_bp.route('/almacenes/<int:id_almacen>/editar', methods=['GET', 'POST'])
def vista_editar_almacen(id_almacen):
    db = SessionLocal()
    almacen = db.query(Almacen).get(id_almacen)
    if not almacen:
        flash("Almacén no encontrado.", "danger")
        return redirect(url_for('inventario_bp.vista_gestionar_almacenes'))
    
    try:
        if request.method == 'POST':
            nombre_almacen_form = request.form.get('nombre_almacen', '').strip()
            descripcion_form = request.form.get('descripcion', '').strip()
            activo_form = 'activo' in request.form

            if not nombre_almacen_form:
                flash("El nombre del almacén es obligatorio.", "danger")
            else:
                if almacen.nombre_almacen.lower() != nombre_almacen_form.lower():
                    existente = db.query(Almacen).filter(Almacen.nombre_almacen.ilike(nombre_almacen_form), Almacen.id_almacen != id_almacen).first()
                    if existente:
                        flash(f"Ya existe otro almacén con el nombre '{nombre_almacen_form}'.", "warning")
                    else:
                        almacen.nombre_almacen = nombre_almacen_form
                
                almacen.descripcion = descripcion_form
                almacen.activo = activo_form
                
                # Usar flash.get_flashed_messages() para verificar si hubo errores antes del commit
                # Esto requiere que 'flash' sea importado de Flask.
                # from flask import flash (ya debería estar al inicio del archivo)
                if not flash.get_flashed_messages(category_filter=["warning", "danger"]): 
                    db.commit()
                    flash(f"Almacén '{almacen.nombre_almacen}' actualizado.", "success")
                    return redirect(url_for('inventario_bp.vista_gestionar_almacenes'))
        
        form_data_repopulate = request.form if request.method == 'POST' else almacen
        return render_template('form_almacen.html',
                               almacen=form_data_repopulate,
                               es_nuevo=False, 
                               titulo_pagina=f"Editar Almacén: {almacen.nombre_almacen}")
    except Exception as e:
        if db.is_active: db.rollback()
        flash(f"Error al editar el almacén: {str(e)}", "danger")
        return redirect(url_for('inventario_bp.vista_gestionar_almacenes'))
    finally:
        db.close()

@inventario_bp.route('/api/buscar-productos', methods=['GET'])
def api_buscar_productos_inventario():
    db = SessionLocal()
    try:
        term = request.args.get('term', '').strip()
        if not term or len(term) < 2:
            return jsonify([])

        productos_encontrados = db.query(Producto.id_producto, Producto.nombre_producto, Producto.sku, Producto.unidad_medida_base)\
            .filter(Producto.activo == True)\
            .filter(or_(
                Producto.nombre_producto.ilike(f"%{term}%"),
                Producto.sku.ilike(f"%{term}%")
            ))\
            .limit(10).all()
        
        resultados = [{"id": p.id_producto, 
                       "text": f"{p.nombre_producto} (SKU: {p.sku or 'N/A'})", # Texto para mostrar en el autocompletar
                       "nombre": p.nombre_producto, # Para llenar el input si es necesario
                       "sku": p.sku or 'N/A',      # Para mostrar en la info seleccionada
                       "unidad_base": p.unidad_medida_base # Para mostrar en la info seleccionada
                       } for p in productos_encontrados]
        return jsonify(resultados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
