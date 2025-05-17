# /mod_test_cotizador/routes.py
from flask import render_template, request, jsonify
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from math import ceil

from . import test_cotizador_bp # Importar el Blueprint

# --- DATOS DE PRUEBA (igual que v3) ---
productos_db_sim = [
    {'id': 'gom1', 'nombre': 'Panditas Clásicos', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom2', 'nombre': 'Gomitas de Frutitas', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom3', 'nombre': 'Gusanos Ácidos', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom4', 'nombre': 'Corazones de Durazno', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom5', 'nombre': 'Mangomitas Enchiladas', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom6', 'nombre': 'Aros de Manzana', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom7', 'nombre': 'Gomitas de Lombriz Neon', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom8', 'nombre': 'Gotitas de Chocolate (Chocoretas)', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom9', 'nombre': 'Dientes de Vampiro', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'gom10', 'nombre': 'Ositos Rojos Enchilados', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'choc1', 'nombre': 'Kisses Hershey\'s (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc2', 'nombre': 'Carlos V Individual (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc3', 'nombre': 'Monedas de Chocolate (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc4', 'nombre': 'Chocoretas (bolsita individual)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc5', 'nombre': 'Bocadín (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc6', 'nombre': 'Mini Mamut (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc7', 'nombre': 'Ferrero Rocher (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc8', 'nombre': 'Conejito Turín (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc9', 'nombre': 'Snickers Mini (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'choc10', 'nombre': 'Paleta Payaso Mini (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'bot1', 'nombre': 'Cacahuates Japoneses', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot2', 'nombre': 'Churritos de Maíz con Chile', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot3', 'nombre': 'Papas Fritas Caseras', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot4', 'nombre': 'Pretzels Salados', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot5', 'nombre': 'Habas Enchiladas', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot6', 'nombre': 'Garbanzos Enchilados', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot7', 'nombre': 'Pistaches con Sal', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot8', 'nombre': 'Semillas de Girasol Saladas', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot9', 'nombre': 'Palomitas de Maíz Naturales', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'bot10', 'nombre': 'Frituras de Harina (Chicharrones)', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'ind1', 'nombre': 'Paleta de Caramelo Grande', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind2', 'nombre': 'Mazapán de la Rosa', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind3', 'nombre': 'Pulparindo Clásico', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind4', 'nombre': 'Bolsita de Skittles', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind5', 'nombre': 'Duvalín Avellana-Vainilla', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind6', 'nombre': 'Glorias de Linares (individual)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind7', 'nombre': 'Pelón Pelo Rico', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind8', 'nombre': 'Chicle Canel\'s (paq. 4)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind9', 'nombre': 'Banderilla de Tamarindo', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'ind10', 'nombre': 'Cucharita de Tamarindo', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'pic1', 'nombre': 'Picafresas (bolsita)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'pic2', 'nombre': 'Rielitos de Tamarindo', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'pic3', 'nombre': 'Miguelito en Polvo (sobre)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'pic4', 'nombre': 'Skwinkles Rellenos (tira)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'pic5', 'nombre': 'Tamaroca (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'pic6', 'nombre': 'Cacahuates Enchilados (a granel)', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'pic7', 'nombre': 'Ollitas de Tamarindo (pieza)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'pic8', 'nombre': 'Lucas Muecas (paleta con chile)', 'unidad_base': 'pieza', 'es_indivisible': True},
    {'id': 'pic9', 'nombre': 'Bolitas de Tamarindo con Chile (a granel)', 'unidad_base': 'g', 'es_indivisible': False},
    {'id': 'pic10', 'nombre': 'Tiritas de Mango Enchilado (a granel)', 'unidad_base': 'g', 'es_indivisible': False},
]

opciones_servicio_config_sim = [
    *[{'id': p['id'], 'nombre_display': p['nombre'], 'id_producto_interno': p['id'], 'cantidad_consumo_base': Decimal('20'), 'unidad_consumo_base': 'g'} for p in productos_db_sim if p['id'].startswith('gom')],
    *[{'id': p['id'], 'nombre_display': p['nombre'], 'id_producto_interno': p['id'], 'cantidad_consumo_base': Decimal('2'), 'unidad_consumo_base': 'pieza'} for p in productos_db_sim if p['id'].startswith('choc')],
    *[{'id': p['id'], 'nombre_display': p['nombre'], 'id_producto_interno': p['id'], 'cantidad_consumo_base': Decimal('25'), 'unidad_consumo_base': 'g'} for p in productos_db_sim if p['id'].startswith('bot')],
    *[{'id': p['id'], 'nombre_display': p['nombre'], 'id_producto_interno': p['id'], 'cantidad_consumo_base': Decimal('1'), 'unidad_consumo_base': 'pieza'} for p in productos_db_sim if p['id'].startswith('ind')],
    *[{'id': p['id'], 'nombre_display': p['nombre'], 'id_producto_interno': p['id'], 'cantidad_consumo_base': Decimal('20') if p['unidad_base'] == 'g' else Decimal('1'), 'unidad_consumo_base': p['unidad_base']} for p in productos_db_sim if p['id'].startswith('pic')],
]
# --- FIN DATOS DE PRUEBA ---

@test_cotizador_bp.route('/')
def vista_test_cotizador():
    return render_template('test_cotizador.html', titulo_pagina="Test Cotizador Mesa de Dulces v4")

@test_cotizador_bp.route('/ping')
def ping_test():
    return "Pong desde test_cotizador_bp!"

@test_cotizador_bp.route('/calcular', methods=['POST'])
def calcular_cantidades_test():
    data = request.json
    if not data:
        return jsonify({"error": "No se recibieron datos JSON"}), 400

    numero_invitados_str = data.get('numero_invitados', '1')
    try:
        numero_invitados = Decimal(numero_invitados_str)
        if numero_invitados <= 0:
            raise ValueError("El número de invitados debe ser positivo.")
    except (ValueError, TypeError):
        return jsonify({"error": "Número de invitados inválido"}), 400

    seleccion_grupos = data.get('seleccion_grupos', {})
    total_grupos_disponibles_payload = Decimal(data.get('total_grupos_disponibles', 1))
    numero_grupos_con_selecciones_payload = Decimal(data.get('numero_grupos_con_selecciones', 1))

    detalles_calculados = []
    resumen_total_insumos = {}
    factor_ajuste_global_de_grupos = Decimal('1')

    if numero_grupos_con_selecciones_payload > Decimal(0) and numero_grupos_con_selecciones_payload < total_grupos_disponibles_payload:
        factor_ajuste_global_de_grupos = total_grupos_disponibles_payload / numero_grupos_con_selecciones_payload
    
    factor_ajuste_global_debug_msg = f"Factor de Ajuste Global de Grupos: {factor_ajuste_global_de_grupos:.2f} (Total Grupos: {total_grupos_disponibles_payload}, Grupos Seleccionados: {numero_grupos_con_selecciones_payload})"
    if numero_grupos_con_selecciones_payload == Decimal(0):
        factor_ajuste_global_debug_msg = "No se seleccionaron opciones de ningún grupo."
    elif factor_ajuste_global_de_grupos == Decimal('1'):
        factor_ajuste_global_debug_msg = "Se seleccionaron opciones de todos los grupos disponibles o solo de un grupo (si solo uno estaba disponible/seleccionado). Sin ajuste global de grupos."

    for id_grupo, grupo_data in seleccion_grupos.items():
        opciones_seleccionadas_ids = grupo_data.get('opciones_seleccionadas_ids', [])
        opciones_permitidas_str = grupo_data.get('opciones_permitidas_en_grupo', '1')
        try:
            opciones_permitidas_en_grupo = Decimal(opciones_permitidas_str)
            if opciones_permitidas_en_grupo <= 0:
                opciones_permitidas_en_grupo = Decimal('1')
        except (ValueError, TypeError):
            opciones_permitidas_en_grupo = Decimal('1')

        num_opciones_realmente_elegidas_en_grupo = Decimal(len(opciones_seleccionadas_ids))

        if num_opciones_realmente_elegidas_en_grupo == Decimal(0):
            continue

        factor_ajuste_intra_grupo = opciones_permitidas_en_grupo / num_opciones_realmente_elegidas_en_grupo

        for opcion_id in opciones_seleccionadas_ids:
            opcion_config = next((o for o in opciones_servicio_config_sim if o['id'] == opcion_id), None)
            if not opcion_config: continue
            producto = next((p for p in productos_db_sim if p['id'] == opcion_config['id_producto_interno']), None)
            if not producto: continue

            try:
                cantidad_consumo_base = Decimal(opcion_config['cantidad_consumo_base'])
            except (ValueError, TypeError): continue

            cantidad_ajustada_por_persona_bruta = cantidad_consumo_base * factor_ajuste_intra_grupo * factor_ajuste_global_de_grupos
            cantidad_ajustada_por_persona_final = cantidad_ajustada_por_persona_bruta # Inicializar

            if producto['es_indivisible']:
                # Para piezas, redondear la cantidad POR PERSONA hacia arriba al siguiente entero
                cantidad_ajustada_por_persona_final = Decimal(ceil(cantidad_ajustada_por_persona_bruta))
            else: # Para gramos y otras unidades divisibles
                # Redondear hacia arriba al siguiente múltiplo de 5
                # (valor / 5) redondeado hacia arriba, luego multiplicado por 5
                cantidad_ajustada_por_persona_final = (cantidad_ajustada_por_persona_bruta / Decimal('5')).quantize(Decimal('1'), rounding=ROUND_CEILING) * Decimal('5')
                # Asegurar que no sea menor que la cantidad ajustada bruta (si ya era múltiplo de 5 y el ROUND_CEILING no lo subió)
                if cantidad_ajustada_por_persona_final < cantidad_ajustada_por_persona_bruta:
                     cantidad_ajustada_por_persona_final = ( (cantidad_ajustada_por_persona_bruta + Decimal('0.00001')) / Decimal('5')).quantize(Decimal('1'), rounding=ROUND_CEILING) * Decimal('5')


            # La cantidad total para el evento se calcula con la cantidad por persona ya redondeada según su tipo
            cantidad_total_evento_final = cantidad_ajustada_por_persona_final * numero_invitados
            # Para piezas, el total ya será entero. Para gramos, podría tener decimales si el redondeo por persona no da entero exacto al multiplicar.

            detalles_calculados.append({
                'nombre_producto': producto['nombre'],
                'cantidad_por_persona': float(cantidad_ajustada_por_persona_final),
                'unidad_base': producto['unidad_base'],
                'cantidad_total_evento': float(cantidad_total_evento_final),
                'debug_factor_intra': float(factor_ajuste_intra_grupo),
                'debug_factor_global': float(factor_ajuste_global_de_grupos)
            })

            if producto['nombre'] not in resumen_total_insumos:
                resumen_total_insumos[producto['nombre']] = {
                    'cantidad': Decimal('0'),
                    'unidad': producto['unidad_base'],
                    'es_indivisible': producto['es_indivisible']
                }
            resumen_total_insumos[producto['nombre']]['cantidad'] += cantidad_total_evento_final

    for nombre_prod, datos_prod in resumen_total_insumos.items():
        if datos_prod['es_indivisible']:
            datos_prod['cantidad'] = Decimal(ceil(datos_prod['cantidad'])) # El total de piezas debe ser entero
        else:
            # Para gramos, el total puede tener decimales, pero podemos aplicar una precisión final
            datos_prod['cantidad'] = datos_prod['cantidad'].quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        datos_prod['cantidad'] = float(datos_prod['cantidad'])

    return jsonify({
        "detalles_calculados": detalles_calculados,
        "resumen_total_insumos": resumen_total_insumos,
        "factor_ajuste_global_debug": factor_ajuste_global_debug_msg
    })
