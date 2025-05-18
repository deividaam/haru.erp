# /mod_proyectos/routes.py
from flask import render_template, request, redirect, url_for, flash
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc, exc as sqlalchemy_exc
from decimal import Decimal
from datetime import date

from . import proyectos_bp  # Importar el blueprint
from database import SessionLocal
from models import Proyecto # Solo necesitamos Proyecto aquí, y Cotizacion para el selectinload

# --- RUTAS PARA PROYECTOS ---
# El prefijo '/proyectos' ya está definido en el Blueprint.

@proyectos_bp.route('/', methods=['GET']) # Ruta base para /proyectos/
def vista_listar_proyectos():
    db = SessionLocal()
    try:
        proyectos = db.query(Proyecto).options(
            selectinload(Proyecto.cotizaciones) # Para mostrar info de cotizaciones en la lista
        ).order_by(desc(Proyecto.fecha_evento)).all()
        return render_template('listar_proyectos.html',
                               proyectos=proyectos,
                               titulo_pagina="Listado de Proyectos")
    except Exception as e:
        flash(f"Error al cargar los proyectos: {str(e)}", "danger")
        return render_template('listar_proyectos.html', proyectos=[], titulo_pagina="Listado de Proyectos")
    finally:
        if db.is_active:
            db.close()

@proyectos_bp.route('/nuevo', methods=['GET', 'POST'])
def vista_crear_proyecto():
    proyecto_data_para_template = {}
    if request.method == 'GET':
        proyecto_data_para_template['fecha_hoy'] = date.today().isoformat()

    if request.method == 'POST':
        db = SessionLocal()
        proyecto_data_para_template = request.form.to_dict()
        if 'fecha_evento' not in proyecto_data_para_template or not proyecto_data_para_template['fecha_evento']:
            proyecto_data_para_template['fecha_hoy'] = date.today().isoformat()
        try:
            identificador_evento_form = request.form.get('identificador_evento', '').strip()
            if not identificador_evento_form:
                flash("El Identificador del Evento es obligatorio.", "danger")
                # No cerrar db aquí, se cierra en finally
                return render_template('crear_editar_proyecto.html', proyecto=proyecto_data_para_template, titulo_pagina="Nuevo Proyecto", es_nuevo=True, fecha_hoy=proyecto_data_para_template.get('fecha_hoy'))

            existente = db.query(Proyecto).filter(Proyecto.identificador_evento == identificador_evento_form).first()
            if existente:
                flash(f"El Identificador del Evento '{identificador_evento_form}' ya existe.", "warning")
                return render_template('crear_editar_proyecto.html', proyecto=proyecto_data_para_template, titulo_pagina="Nuevo Proyecto", es_nuevo=True, fecha_hoy=proyecto_data_para_template.get('fecha_hoy'))

            fecha_evento_str = request.form.get('fecha_evento')
            if not fecha_evento_str:
                 flash("La Fecha del Evento es obligatoria.", "danger")
                 return render_template('crear_editar_proyecto.html', proyecto=proyecto_data_para_template, titulo_pagina="Nuevo Proyecto", es_nuevo=True, fecha_hoy=proyecto_data_para_template.get('fecha_hoy'))

            fecha_evento_obj = date.fromisoformat(fecha_evento_str)
            numero_invitados_val = request.form.get('numero_invitados')
            numero_invitados_obj = int(numero_invitados_val) if numero_invitados_val and numero_invitados_val.isdigit() else None

            costo_transporte_str = request.form.get('costo_transporte_estimado', '0.00')
            costo_viaticos_str = request.form.get('costo_viaticos_estimado', '0.00')
            costo_hospedaje_str = request.form.get('costo_hospedaje_estimado', '0.00')

            nuevo_proyecto = Proyecto(
                identificador_evento=identificador_evento_form,
                nombre_evento=request.form.get('nombre_evento', '').strip(),
                fecha_evento=fecha_evento_obj,
                numero_invitados=numero_invitados_obj,
                cliente_nombre=request.form.get('cliente_nombre', '').strip(),
                cliente_telefono=request.form.get('cliente_telefono', '').strip(),
                cliente_email=request.form.get('cliente_email', '').strip(),
                direccion_evento=request.form.get('direccion_evento', '').strip(),
                tipo_ubicacion=request.form.get('tipo_ubicacion', 'Local (CDMX y Área Metropolitana)'),
                costo_transporte_estimado=Decimal(costo_transporte_str) if costo_transporte_str else Decimal('0.00'),
                costo_viaticos_estimado=Decimal(costo_viaticos_str) if costo_viaticos_str else Decimal('0.00'),
                costo_hospedaje_estimado=Decimal(costo_hospedaje_str) if costo_hospedaje_str else Decimal('0.00'),
                notas_proyecto=request.form.get('notas_proyecto', '').strip()
            )
            db.add(nuevo_proyecto)
            db.commit()
            flash(f"Proyecto '{nuevo_proyecto.nombre_evento}' creado exitosamente.", "success")

            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            else:
                # Redirigir a la lista de proyectos del blueprint
                return redirect(url_for('proyectos_bp.vista_listar_proyectos'))
        except (ValueError, sqlalchemy_exc.IntegrityError) as e_val_int:
            if db.is_active: db.rollback()
            flash(f"Error en datos o identificador duplicado: {str(e_val_int)}", "danger")
        except Exception as e:
            if db.is_active: db.rollback()
            flash(f"Error al crear el proyecto: {str(e)}", "danger")
        finally:
            if db.is_active: db.close()
        return render_template('crear_editar_proyecto.html', proyecto=proyecto_data_para_template, titulo_pagina="Nuevo Proyecto", es_nuevo=True, fecha_hoy=proyecto_data_para_template.get('fecha_hoy'))

    return render_template('crear_editar_proyecto.html', proyecto=proyecto_data_para_template, titulo_pagina="Nuevo Proyecto", es_nuevo=True)

@proyectos_bp.route('/<int:id_proyecto>/editar', methods=['GET', 'POST'])
def vista_editar_proyecto(id_proyecto):
    db = SessionLocal()
    proyecto_a_editar = db.query(Proyecto).get(id_proyecto)
    if not proyecto_a_editar:
        flash("Proyecto no encontrado.", "danger")
        if db.is_active: db.close()
        return redirect(url_for('proyectos_bp.vista_listar_proyectos'))

    if request.method == 'POST':
        try:
            identificador_evento_form = request.form.get('identificador_evento', '').strip()
            if not identificador_evento_form:
                flash("El Identificador del Evento es obligatorio.", "danger")
                return render_template('crear_editar_proyecto.html', proyecto=proyecto_a_editar, titulo_pagina=f"Editar Proyecto: {proyecto_a_editar.nombre_evento}", es_nuevo=False, id_proyecto=id_proyecto)

            if proyecto_a_editar.identificador_evento != identificador_evento_form:
                existente = db.query(Proyecto).filter(Proyecto.identificador_evento == identificador_evento_form, Proyecto.id_proyecto != id_proyecto).first()
                if existente:
                    flash(f"El Identificador del Evento '{identificador_evento_form}' ya existe para otro proyecto.", "warning")
                    return render_template('crear_editar_proyecto.html', proyecto=request.form, titulo_pagina=f"Editar Proyecto: {proyecto_a_editar.nombre_evento}", es_nuevo=False, id_proyecto=id_proyecto)

            fecha_evento_str = request.form.get('fecha_evento')
            if not fecha_evento_str:
                 flash("La Fecha del Evento es obligatoria.", "danger")
                 return render_template('crear_editar_proyecto.html', proyecto=proyecto_a_editar, titulo_pagina=f"Editar Proyecto: {proyecto_a_editar.nombre_evento}", es_nuevo=False, id_proyecto=id_proyecto)

            proyecto_a_editar.identificador_evento = identificador_evento_form
            proyecto_a_editar.nombre_evento = request.form.get('nombre_evento', '').strip()
            proyecto_a_editar.fecha_evento = date.fromisoformat(fecha_evento_str)
            numero_invitados_val = request.form.get('numero_invitados')
            proyecto_a_editar.numero_invitados = int(numero_invitados_val) if numero_invitados_val and numero_invitados_val.isdigit() else None
            proyecto_a_editar.cliente_nombre = request.form.get('cliente_nombre', '').strip()
            proyecto_a_editar.cliente_telefono = request.form.get('cliente_telefono', '').strip()
            proyecto_a_editar.cliente_email = request.form.get('cliente_email', '').strip()
            proyecto_a_editar.direccion_evento = request.form.get('direccion_evento', '').strip()
            proyecto_a_editar.tipo_ubicacion = request.form.get('tipo_ubicacion', 'Local (CDMX y Área Metropolitana)')
            costo_transporte_str = request.form.get('costo_transporte_estimado', '0.00')
            proyecto_a_editar.costo_transporte_estimado = Decimal(costo_transporte_str) if costo_transporte_str else Decimal('0.00')
            costo_viaticos_str = request.form.get('costo_viaticos_estimado', '0.00')
            proyecto_a_editar.costo_viaticos_estimado = Decimal(costo_viaticos_str) if costo_viaticos_str else Decimal('0.00')
            costo_hospedaje_str = request.form.get('costo_hospedaje_estimado', '0.00')
            proyecto_a_editar.costo_hospedaje_estimado = Decimal(costo_hospedaje_str) if costo_hospedaje_str else Decimal('0.00')
            proyecto_a_editar.notas_proyecto = request.form.get('notas_proyecto', '').strip()

            db.commit()
            flash(f"Proyecto '{proyecto_a_editar.nombre_evento}' actualizado exitosamente.", "success")
            # Redirigir a la vista de detalle del blueprint
            return redirect(url_for('proyectos_bp.vista_detalle_proyecto', id_proyecto=id_proyecto))
        except (ValueError, sqlalchemy_exc.IntegrityError) as e_val_int:
            if db.is_active: db.rollback()
            flash(f"Error en datos o identificador duplicado al editar: {str(e_val_int)}", "danger")
        except Exception as e:
            if db.is_active: db.rollback()
            flash(f"Error al actualizar el proyecto: {str(e)}", "danger")
        finally:
            if db.is_active: db.close()
        return render_template('crear_editar_proyecto.html', proyecto=request.form if request.form else proyecto_a_editar, titulo_pagina=f"Editar Proyecto: {proyecto_a_editar.nombre_evento}", es_nuevo=False, id_proyecto=id_proyecto)

    if db.is_active: db.close()
    return render_template('crear_editar_proyecto.html', proyecto=proyecto_a_editar, titulo_pagina=f"Editar Proyecto: {proyecto_a_editar.nombre_evento}", es_nuevo=False, id_proyecto=id_proyecto)

@proyectos_bp.route('/<int:id_proyecto>', methods=['GET']) # Ruta para /proyectos/<id_proyecto>
def vista_detalle_proyecto(id_proyecto):
    db = SessionLocal()
    try:
        proyecto = db.query(Proyecto).options(
            selectinload(Proyecto.cotizaciones) # Para mostrar cotizaciones asociadas
        ).get(id_proyecto)
        if not proyecto:
            flash("Proyecto no encontrado.", "danger")
            return redirect(url_for('proyectos_bp.vista_listar_proyectos'))
        return render_template('detalle_proyecto.html',
                               proyecto=proyecto,
                               titulo_pagina=f"Detalle Proyecto: {proyecto.nombre_evento}")
    except Exception as e:
        flash(f"Error al cargar el detalle del proyecto: {str(e)}", "danger")
        return redirect(url_for('proyectos_bp.vista_listar_proyectos'))
    finally:
        if db.is_active:
            db.close()
