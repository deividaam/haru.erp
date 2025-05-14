# utils_carga.py
import csv
from sqlalchemy.orm import Session
from models import Categoria, Subcategoria, Producto, ContadorSKU, Proveedor, PrecioProveedor
from datetime import date, datetime

MAPEO_CATEGORIA_PREFIJO_SKU = {
    "Dulces/Golosinas": "DG",
    "Globos": "GL",
    "Decoración": "DE",
    "Contenedores/Exhibidores": "DI", # Mapeo para una posible categoría con este nombre exacto
    "Display": "DI", # Mantenemos este por si se usa "Display" como nombre de categoría en el CSV
    "Servicios": "SE"
}

# --- Definición de campos CSV obligatorios por categoría ---
# Las claves deben coincidir con los nombres de categoría como aparecen en el CSV.
# Los valores deben ser los nombres exactos de las columnas CSV.
CAMPOS_OBLIGATORIOS_CSV_POR_CATEGORIA = {
    "Dulces/Golosinas": ["Subcategoria", "Presentacion", "CantidadPorPresentacion", "UnidadMedidaVenta", "Sabor", "DiasAnticipacionCompra"],
    "Globos": ["Subcategoria", "Presentacion", "CantidadPorPresentacion", "UnidadMedidaVenta", "Color", "TamanoPulgadas", "DiasAnticipacionCompra"],
    "Decoración": ["Subcategoria", "Presentacion", "CantidadPorPresentacion", "Color", "DiasAnticipacionCompra"],
    "Display": ["Subcategoria", "Presentacion", "CantidadPorPresentacion", "Color", "Material", "DiasAnticipacionCompra"],
    "Contenedores/Exhibidores": ["Subcategoria", "Presentacion", "CantidadPorPresentacion", "Color", "Material", "DiasAnticipacionCompra"],
    "Servicios": ["Subcategoria", "ModalidadServicio", "DescripcionAdicional", "DiasAnticipacionCompra"]
}
# Columnas CSV que siempre son obligatorias, independientemente de la categoría
COLUMNAS_CSV_SIEMPRE_OBLIGATORIAS = ["NombreProducto", "Categoria"]


def get_or_create_categoria(db: Session, nombre_cat: str, prefijo_sugerido: str = None) -> Categoria:
    categoria = db.query(Categoria).filter(Categoria.nombre_categoria == nombre_cat).first()
    if not categoria:
        print(f"Creando nueva categoría: {nombre_cat} con prefijo {prefijo_sugerido or 'N/A'}")
        categoria = Categoria(nombre_categoria=nombre_cat, prefijo_sku=prefijo_sugerido)
        db.add(categoria)
        db.flush()
        contador = ContadorSKU(id_categoria=categoria.id_categoria, ultimo_valor=0)
        db.add(contador)
        db.flush()
    elif not categoria.prefijo_sku and prefijo_sugerido:
        print(f"Actualizando prefijo para categoría existente '{nombre_cat}' a '{prefijo_sugerido}'")
        categoria.prefijo_sku = prefijo_sugerido
        db.flush()
        contador_existente = db.query(ContadorSKU).filter_by(id_categoria=categoria.id_categoria).first()
        if not contador_existente:
            contador = ContadorSKU(id_categoria=categoria.id_categoria, ultimo_valor=0)
            db.add(contador)
            db.flush()
    return categoria


def get_or_create_subcategoria(db: Session, categoria_obj: Categoria, nombre_subcat: str) -> Subcategoria | None:
    if not nombre_subcat or not nombre_subcat.strip():
        return None
    subcategoria = db.query(Subcategoria).filter(
        Subcategoria.nombre_subcategoria == nombre_subcat,
        Subcategoria.id_categoria == categoria_obj.id_categoria
    ).first()
    if not subcategoria:
        print(f"Creando nueva subcategoría: {nombre_subcat} en {categoria_obj.nombre_categoria}")
        subcategoria = Subcategoria(nombre_subcategoria=nombre_subcat, id_categoria=categoria_obj.id_categoria)
        db.add(subcategoria)
        db.flush()
    return subcategoria

def generar_siguiente_sku(db: Session, categoria_obj: Categoria) -> str | None:
    if not categoria_obj or not categoria_obj.prefijo_sku:
        print(f"Error: La categoría '{categoria_obj.nombre_categoria if categoria_obj else 'Desconocida'}' no tiene un prefijo SKU definido.")
        return None
    contador = db.query(ContadorSKU).filter(ContadorSKU.id_categoria == categoria_obj.id_categoria).with_for_update().first()
    if not contador:
        print(f"Error: No se encontró contador SKU para la categoría ID {categoria_obj.id_categoria}. Creando uno.")
        contador = ContadorSKU(id_categoria=categoria_obj.id_categoria, ultimo_valor=0)
        db.add(contador)
        db.flush()
    contador.ultimo_valor += 1
    db.flush()
    numero_secuencial = str(contador.ultimo_valor).zfill(5)
    return f"{categoria_obj.prefijo_sku}-{numero_secuencial}"


def construir_descripcion_completa(prod_data: dict) -> str:
    partes = [
        prod_data.get("nombre_producto", ""), # Usar el nombre del producto del diccionario
        prod_data.get("color", ""),
        prod_data.get("sabor", ""),
        prod_data.get("material", ""),
        prod_data.get("tamano_pulgadas", ""),
        prod_data.get("dimensiones_capacidad", ""),
        prod_data.get("tema_estilo", ""),
        prod_data.get("forma_tipo", ""),
        prod_data.get("presentacion", ""),
        prod_data.get("cantidad_por_presentacion", "")
    ]
    # Filtrar valores None o vacíos y luego unir. Asegurarse que todos sean strings.
    return " ".join(filter(None, [str(p).strip() if p is not None else '' for p in partes])).strip()


def parsear_y_validar_csv_productos(stream_archivo_csv):
    productos_para_cargar = []
    errores_filas = []
    line_number_for_error_reporting = 1

    try:
        # Decodificar el stream y manejar el BOM
        decoded_lines = [line.decode('utf-8-sig').rstrip('\r\n') for line in stream_archivo_csv]
        if not decoded_lines:
            return {"productos_listos": [], "errores": [{"fila": 1, "error": "Archivo CSV vacío.", "datos": {}}]}

        # El BOM ya no debería estar en la primera línea si se manejó con utf-8-sig
        reader = csv.DictReader(decoded_lines)

        if not reader.fieldnames:
            return {"productos_listos": [], "errores": [{"fila": 1, "error": "No se pudieron leer los encabezados del CSV.", "datos": {}}]}

        # Lista completa de encabezados esperados según el archivo HTML de instrucciones
        expected_fieldnames_from_instructions = [
            "NombreProducto", "Categoria", "Subcategoria", "DescripcionAdicional",
            "Presentacion", "CantidadPorPresentacion", "UnidadMedidaVenta", "Sabor",
            "Color", "TamanoPulgadas", "Material", "DimensionesCapacidad",
            "TemaEstilo", "ModalidadServicio", "FormaTipo", "DiasAnticipacionCompra"
        ]
        # Verificar que todos los encabezados esperados estén presentes
        missing_headers = [h for h in expected_fieldnames_from_instructions if h not in reader.fieldnames]
        if missing_headers:
            errores_filas.append({"fila": 1, "error": f"Faltan los siguientes encabezados obligatorios en el CSV: {', '.join(missing_headers)}", "datos": {"encabezados_detectados": reader.fieldnames}})
            return {"productos_listos": [], "errores": errores_filas}


        for row_data_raw in reader:
            line_number_for_error_reporting += 1
            # Limpiar espacios en claves y valores
            row_data = {key.strip(): str(value).strip() if value is not None else '' for key, value in row_data_raw.items()}
            fila_valida = True
            errores_esta_fila = []

            # 1. Validar campos siempre obligatorios
            for campo_csv in COLUMNAS_CSV_SIEMPRE_OBLIGATORIAS:
                if not row_data.get(campo_csv):
                    errores_esta_fila.append(f"Falta valor para columna obligatoria '{campo_csv}'.")
                    fila_valida = False

            if not fila_valida:
                errores_filas.append({"fila": line_number_for_error_reporting, "error": "; ".join(errores_esta_fila), "datos": row_data_raw})
                continue # Saltar al siguiente producto si los campos base no están

            nombre_cat_csv = row_data.get('Categoria') # Ya sabemos que existe y tiene valor por la validación anterior

            # 2. Validar campos obligatorios específicos de la categoría
            campos_obligatorios_categoria = CAMPOS_OBLIGATORIOS_CSV_POR_CATEGORIA.get(nombre_cat_csv)
            if campos_obligatorios_categoria:
                for campo_csv in campos_obligatorios_categoria:
                    if not row_data.get(campo_csv): # Si la columna existe pero el valor está vacío
                        errores_esta_fila.append(f"Falta valor para columna '{campo_csv}', obligatoria para la categoría '{nombre_cat_csv}'.")
                        fila_valida = False
            
            if not fila_valida:
                errores_filas.append({"fila": line_number_for_error_reporting, "error": "; ".join(errores_esta_fila), "datos": row_data_raw})
                continue

            # 3. Validar prefijo SKU
            prefijo_sku_sugerido = MAPEO_CATEGORIA_PREFIJO_SKU.get(nombre_cat_csv)
            if not prefijo_sku_sugerido:
                errores_filas.append({"fila": line_number_for_error_reporting, "error": f"Categoría '{nombre_cat_csv}' no tiene un prefijo SKU definido en el mapeo interno.", "datos": row_data_raw})
                continue

            # 4. Procesar campos opcionales y construir el diccionario del producto
            dias_anticipacion = None
            dias_anticipacion_str = row_data.get('DiasAnticipacionCompra', '')
            if dias_anticipacion_str:
                try:
                    dias_anticipacion = int(dias_anticipacion_str)
                    if dias_anticipacion < 0:
                         errores_filas.append({"fila": line_number_for_error_reporting, "error": f"'DiasAnticipacionCompra' no puede ser negativo.", "datos": row_data_raw})
                         continue
                except ValueError:
                    errores_filas.append({"fila": line_number_for_error_reporting, "error": f"Valor no numérico para 'DiasAnticipacionCompra': '{dias_anticipacion_str}'.", "datos": row_data_raw})
                    continue # Saltar este producto si el valor no es numérico

            producto_info = {
                "nombre_producto": row_data.get('NombreProducto'), # Ya validado
                "nombre_categoria_csv": nombre_cat_csv, # Ya validado
                "nombre_subcategoria": row_data.get('Subcategoria'), # Validado por categoría si es obligatorio
                "prefijo_sku_sugerido": prefijo_sku_sugerido, # Ya validado
                "descripcion_adicional": row_data.get('DescripcionAdicional'),
                "presentacion": row_data.get('Presentacion'),
                "cantidad_por_presentacion": row_data.get('CantidadPorPresentacion'),
                "unidad_medida_venta": row_data.get('UnidadMedidaVenta'),
                "sabor": row_data.get('Sabor'),
                "color": row_data.get('Color'),
                "tamano_pulgadas": row_data.get('TamanoPulgadas'),
                "material": row_data.get('Material'),
                "dimensiones_capacidad": row_data.get('DimensionesCapacidad'),
                "tema_estilo": row_data.get('TemaEstilo'),
                "modalidad_servicio": row_data.get('ModalidadServicio'),
                "forma_tipo": row_data.get('FormaTipo'),
                "dias_anticipacion_compra": dias_anticipacion,
                "activo": True
            }
            productos_para_cargar.append(producto_info)

        return {"productos_listos": productos_para_cargar, "errores": errores_filas}

    except csv.Error as e_csv: # Captura errores específicos de CSV
        print(f"Error de formato CSV: {str(e_csv)}")
        return {"productos_listos": [], "errores": [{"fila": line_number_for_error_reporting, "error": f"Error de formato en el archivo CSV: {str(e_csv)}", "datos": {}}]}
    except Exception as e_file:
        print(f"Error al parsear el stream del CSV: {str(e_file)}")
        return {"productos_listos": [], "errores": [{"fila": 1, "error": f"Error general al leer el archivo: {str(e_file)}", "datos": {}}]}


def guardar_productos_en_bd(db: Session, productos_a_guardar: list):
    productos_guardados_count = 0
    productos_existentes_count = 0
    errores_guardado = []

    if not productos_a_guardar:
        return {"guardados": 0, "existentes": 0, "errores_detalle_guardado": ["No hay productos para guardar."]}

    for prod_data in productos_a_guardar:
        try:
            nombre_cat_csv = prod_data["nombre_categoria_csv"]
            prefijo_sugerido = prod_data["prefijo_sku_sugerido"]

            categoria_obj = get_or_create_categoria(db, nombre_cat_csv, prefijo_sugerido)
            subcategoria_obj = None
            if prod_data.get("nombre_subcategoria"): # Usar .get() por si no viene
                subcategoria_obj = get_or_create_subcategoria(db, categoria_obj, prod_data["nombre_subcategoria"])

            nuevo_sku = generar_siguiente_sku(db, categoria_obj)
            if not nuevo_sku:
                errores_guardado.append(f"No se pudo generar SKU para '{prod_data['nombre_producto']}' en categoría '{nombre_cat_csv}'. Producto no guardado.")
                db.rollback()
                continue

            producto_existente = db.query(Producto).filter(Producto.sku == nuevo_sku).first()
            if producto_existente:
                print(f"Advertencia: SKU generado '{nuevo_sku}' para '{prod_data['nombre_producto']}' ya existe. Omitiendo.")
                errores_guardado.append(f"SKU '{nuevo_sku}' ya existe para '{producto_existente.nombre_producto}'. Se omitió '{prod_data['nombre_producto']}'.")
                productos_existentes_count += 1
                db.rollback()
                continue

            # Crear un diccionario solo con los campos que el modelo Producto espera y que tienen valor
            campos_modelo_producto = {
                "nombre_producto": prod_data["nombre_producto"],
                "sku": nuevo_sku,
                "id_categoria_directa": categoria_obj.id_categoria if not subcategoria_obj else None,
                "id_subcategoria": subcategoria_obj.id_subcategoria if subcategoria_obj else None,
                "activo": prod_data.get("activo", True)
            }
            # Añadir campos opcionales solo si tienen valor en prod_data
            opcionales_directos = [
                "descripcion_adicional", "presentacion", "cantidad_por_presentacion",
                "unidad_medida_venta", "sabor", "color", "tamano_pulgadas", "material",
                "dimensiones_capacidad", "tema_estilo", "modalidad_servicio", "forma_tipo",
                "dias_anticipacion_compra"
            ]
            for campo in opcionales_directos:
                if prod_data.get(campo): # Si existe y no está vacío
                    campos_modelo_producto[campo] = prod_data[campo]
            
            # Construir descripción completa con los datos que se van a guardar
            campos_modelo_producto["descripcion_completa_generada"] = construir_descripcion_completa(campos_modelo_producto)


            nuevo_producto = Producto(**campos_modelo_producto)
            db.add(nuevo_producto)
            productos_guardados_count += 1
        except Exception as e_save:
            db.rollback()
            errores_guardado.append(f"Error al guardar '{prod_data.get('nombre_producto', 'Desconocido')}': {str(e_save)}")
            continue

    try:
        if productos_guardados_count > 0:
            db.commit()
    except Exception as e_commit:
        db.rollback()
        errores_guardado.append(f"Error al hacer commit final a la BD: {str(e_commit)}")
        # Resetear contador si el commit falla para reflejar que no se guardaron
        productos_guardados_count = 0

    mensaje_final = f"Guardado finalizado. Nuevos: {productos_guardados_count}. Existentes/Omitidos por SKU duplicado: {productos_existentes_count}."
    if errores_guardado:
        mensaje_final += f" Errores/Advertencias durante el guardado: {len(errores_guardado)}."

    return {
        "mensaje": mensaje_final,
        "guardados": productos_guardados_count,
        "existentes_omitidos": productos_existentes_count,
        "errores_detalle_guardado": errores_guardado
    }


def parsear_y_validar_csv_precios(db: Session, stream_archivo_csv):
    precios_para_cargar = []
    errores_filas = []
    line_number = 1

    try:
        decoded_lines = [line.decode('utf-8-sig').rstrip('\r\n') for line in stream_archivo_csv]
        if not decoded_lines:
            return {"precios_listos": [], "errores": [{"fila": 1, "error": "Archivo CSV de precios vacío.", "datos": {}}]}

        reader = csv.DictReader(decoded_lines)

        if not reader.fieldnames:
            return {"precios_listos": [], "errores": [{"fila": 1, "error": "No se pudieron leer los encabezados del CSV de precios.", "datos": {}}]}

        expected_headers = ["SKUProducto", "NombreProveedor", "PrecioCompra"] # Mínimos
        if not all(header in reader.fieldnames for header in expected_headers):
            missing = [h for h in expected_headers if h not in reader.fieldnames]
            errores_filas.append({"fila": 1, "error": f"Faltan encabezados obligatorios en CSV de precios: {', '.join(missing)}.", "datos": {"encabezados_detectados": reader.fieldnames}})
            return {"precios_listos": [], "errores": errores_filas}

        for row_data_raw in reader:
            line_number += 1
            row_data = {key.strip(): str(value).strip() if value is not None else '' for key, value in row_data_raw.items()}
            fila_valida_precio = True
            errores_esta_fila_precio = []

            sku_producto = row_data.get("SKUProducto")
            nombre_proveedor = row_data.get("NombreProveedor")
            precio_compra_str = row_data.get("PrecioCompra")
            fecha_vigencia_str = row_data.get("FechaVigencia", "")
            notas_precio = row_data.get("NotasPrecio", "")

            if not sku_producto:
                errores_esta_fila_precio.append("Falta 'SKUProducto'.")
                fila_valida_precio = False
            if not nombre_proveedor:
                errores_esta_fila_precio.append("Falta 'NombreProveedor'.")
                fila_valida_precio = False
            if not precio_compra_str:
                errores_esta_fila_precio.append("Falta 'PrecioCompra'.")
                fila_valida_precio = False

            if not fila_valida_precio:
                errores_filas.append({"fila": line_number, "error": "; ".join(errores_esta_fila_precio), "datos": row_data_raw})
                continue

            try:
                precio_compra = float(precio_compra_str)
                if precio_compra <= 0:
                    errores_filas.append({"fila": line_number, "error": "'PrecioCompra' debe ser un número positivo.", "datos": row_data_raw})
                    continue
            except ValueError:
                errores_filas.append({"fila": line_number, "error": "'PrecioCompra' debe ser un número.", "datos": row_data_raw})
                continue

            fecha_vigencia = None
            if fecha_vigencia_str:
                try:
                    fecha_vigencia = date.fromisoformat(fecha_vigencia_str)
                except ValueError:
                    errores_filas.append({"fila": line_number, "error": "Formato de 'FechaVigencia' inválido (debe ser AAAA-MM-DD). Se usará fecha actual.", "datos": row_data_raw})
                    # No continuar, pero se usará fecha actual en el guardado si fecha_vigencia es None

            producto_db = db.query(Producto).filter(Producto.sku == sku_producto).first()
            if not producto_db:
                errores_filas.append({"fila": line_number, "error": f"Producto con SKU '{sku_producto}' no encontrado.", "datos": row_data_raw})
                continue

            proveedor_db = db.query(Proveedor).filter(Proveedor.nombre_proveedor == nombre_proveedor).first()
            if not proveedor_db:
                errores_filas.append({"fila": line_number, "error": f"Proveedor con nombre '{nombre_proveedor}' no encontrado.", "datos": row_data_raw})
                continue

            unidad_compra_final = producto_db.presentacion or "Unidad"

            precio_existente = db.query(PrecioProveedor).filter_by(
                id_producto=producto_db.id_producto,
                id_proveedor=proveedor_db.id_proveedor
            ).first()
            accion = "Actualizar" if precio_existente else "Nuevo"

            precios_para_cargar.append({
                "id_producto": producto_db.id_producto,
                "sku_producto": sku_producto,
                "id_proveedor": proveedor_db.id_proveedor,
                "nombre_proveedor": nombre_proveedor,
                "precio_compra": precio_compra,
                "unidad_compra_proveedor": unidad_compra_final,
                "fecha_vigencia": fecha_vigencia,
                "fecha_vigencia_str": fecha_vigencia.isoformat() if fecha_vigencia else date.today().isoformat(), # Para mostrar en confirmación
                "notas_precio": notas_precio or None,
                "accion": accion
            })

        return {"precios_listos": precios_para_cargar, "errores": errores_filas}
    except csv.Error as e_csv:
        print(f"Error de formato CSV en precios: {str(e_csv)}")
        return {"precios_listos": [], "errores": [{"fila": line_number, "error": f"Error de formato en el archivo CSV de precios: {str(e_csv)}", "datos": {}}]}
    except Exception as e:
        print(f"Error al parsear CSV de precios: {e}")
        return {"precios_listos": [], "errores": [{"fila": 1, "error": f"Error general al leer el archivo de precios: {str(e)}", "datos": {}}]}


def guardar_precios_en_bd(db: Session, precios_a_procesar: list):
    precios_actualizados_count = 0
    precios_creados_count = 0
    errores_guardado_precios = []

    if not precios_a_procesar:
        return {"mensaje": "No hay precios para procesar."}

    for precio_data in precios_a_procesar:
        try:
            # Si fecha_vigencia no se pudo parsear (es None), usar la fecha de hoy
            fecha_a_usar = precio_data.get("fecha_vigencia") or date.today()

            precio_existente = db.query(PrecioProveedor).filter_by(
                id_producto=precio_data["id_producto"],
                id_proveedor=precio_data["id_proveedor"]
            ).first()

            if precio_existente:
                precio_existente.precio_compra = precio_data["precio_compra"]
                precio_existente.unidad_compra_proveedor = precio_data["unidad_compra_proveedor"]
                precio_existente.fecha_actualizacion_precio = fecha_a_usar
                precio_existente.notas = precio_data.get("notas_precio")
                precios_actualizados_count += 1
            else:
                nuevo_precio = PrecioProveedor(
                    id_producto=precio_data["id_producto"],
                    id_proveedor=precio_data["id_proveedor"],
                    precio_compra=precio_data["precio_compra"],
                    unidad_compra_proveedor=precio_data["unidad_compra_proveedor"],
                    fecha_actualizacion_precio=fecha_a_usar,
                    notas=precio_data.get("notas_precio")
                )
                db.add(nuevo_precio)
                precios_creados_count += 1
        except Exception as e_save_precio:
            db.rollback()
            errores_guardado_precios.append(f"Error procesando precio para SKU {precio_data.get('sku_producto')} y Prov {precio_data.get('nombre_proveedor')}: {str(e_save_precio)}")
            continue

    try:
        if precios_creados_count > 0 or precios_actualizados_count > 0:
            db.commit()
    except Exception as e_commit_precio:
        db.rollback()
        errores_guardado_precios.append(f"Error al hacer commit final a la BD para precios: {str(e_commit_precio)}")
        precios_creados_count = 0
        precios_actualizados_count = 0

    mensaje = f"Proceso de precios finalizado. Nuevos: {precios_creados_count}, Actualizados: {precios_actualizados_count}."
    if errores_guardado_precios:
        mensaje += f" Errores durante el guardado: {len(errores_guardado_precios)}."
        # Podrías añadir los detalles de errores_guardado_precios al mensaje si es necesario para el flash

    return {"mensaje": mensaje} # Podrías también devolver los errores detallados si quieres mostrarlos
