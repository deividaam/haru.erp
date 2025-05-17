# utils_carga.py
import csv
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session
from sqlalchemy import exc as sqlalchemy_exc

# Asegúrate de importar los modelos actualizados
from models import Categoria, Subcategoria, Producto, ContadorSKU # Proveedor, PrecioProveedor (si se usan en otras funciones)

# Este mapeo sigue siendo útil si se crean categorías principales nuevas desde el CSV
# y se quiere asignarles un prefijo SKU automáticamente.
MAPEO_CATEGORIA_PREFIJO_SKU = {
    "Dulces/Golosinas": "DG",
    "Globos": "GL",
    "Decoración": "DE",
    "Display": "DI", # Mantenemos "Display" y "Contenedores/Exhibidores" si son sinónimos
    "Contenedores/Exhibidores": "DI",
    "Servicios": "SE" # Para productos que son servicios directos
    # Añade otras categorías principales y sus prefijos aquí
}

# --- Funciones de Ayuda para Categorización Jerárquica ---

def get_or_create_categoria_principal(db: Session, nombre_cat_principal: str) -> Categoria | None:
    """
    Obtiene o crea una categoría principal (sin padre).
    Asigna un prefijo SKU si es nueva y está en MAPEO_CATEGORIA_PREFIJO_SKU.
    """
    if not nombre_cat_principal:
        return None
    
    categoria = db.query(Categoria).filter(
        Categoria.nombre_categoria == nombre_cat_principal,
        Categoria.id_categoria_padre == None # Asegurar que es de nivel superior
    ).first()
    
    if not categoria:
        prefijo_sugerido = MAPEO_CATEGORIA_PREFIJO_SKU.get(nombre_cat_principal)
        # Solo crear si tenemos un prefijo, o decidir una política diferente
        if not prefijo_sugerido:
            print(f"Advertencia: Categoría principal '{nombre_cat_principal}' no tiene prefijo SKU en mapeo y no se creará automáticamente sin él.")
            return None # O podrías decidir crearla sin prefijo si esa es tu política

        print(f"Creando nueva categoría principal: {nombre_cat_principal} con prefijo {prefijo_sugerido}")
        categoria = Categoria(
            nombre_categoria=nombre_cat_principal,
            prefijo_sku=prefijo_sugerido
        )
        db.add(categoria)
        try:
            db.flush() # Para obtener el ID de la categoría para el contador
            contador = ContadorSKU(id_categoria=categoria.id_categoria, ultimo_valor=0)
            db.add(contador)
            db.flush()
        except sqlalchemy_exc.IntegrityError: # Podría haber un problema si el prefijo no es único
            db.rollback()
            print(f"Error de integridad al crear categoría principal '{nombre_cat_principal}' o su contador. ¿Prefijo duplicado?")
            return None
    elif not categoria.prefijo_sku: # Si existe pero no tiene prefijo, intentar asignarlo
        prefijo_sugerido = MAPEO_CATEGORIA_PREFIJO_SKU.get(nombre_cat_principal)
        if prefijo_sugerido:
            categoria.prefijo_sku = prefijo_sugerido
            # Asegurar contador si no existe
            contador_existente = db.query(ContadorSKU).filter_by(id_categoria=categoria.id_categoria).first()
            if not contador_existente:
                contador = ContadorSKU(id_categoria=categoria.id_categoria, ultimo_valor=0)
                db.add(contador)
            try:
                db.flush()
            except Exception as e_flush:
                db.rollback()
                print(f"Error al actualizar prefijo o contador para categoría '{nombre_cat_principal}': {e_flush}")
                return None # O devolver la categoría sin el prefijo actualizado
    return categoria

def get_or_create_subcategoria_anidada(db: Session, nombre_subcat: str, cat_principal_obj: Categoria = None, subcat_padre_obj: Subcategoria = None) -> Subcategoria | None:
    """
    Obtiene o crea una subcategoría, que puede estar bajo una Categoria principal
    o bajo otra Subcategoria.
    """
    if not nombre_subcat:
        return None

    query = db.query(Subcategoria).filter(Subcategoria.nombre_subcategoria == nombre_subcat)
    
    if cat_principal_obj and not subcat_padre_obj: # Hija directa de una Categoria
        query = query.filter(Subcategoria.id_categoria_contenedora == cat_principal_obj.id_categoria,
                             Subcategoria.id_subcategoria_padre == None)
    elif subcat_padre_obj and not cat_principal_obj: # Hija directa de otra Subcategoria
        query = query.filter(Subcategoria.id_subcategoria_padre == subcat_padre_obj.id_subcategoria,
                             Subcategoria.id_categoria_contenedora == None) # O podría heredar la cat_contenedora del padre
    elif cat_principal_obj and subcat_padre_obj: # Hija de Subcategoria, pero también sabemos su Categoria raíz (para consistencia)
        query = query.filter(Subcategoria.id_subcategoria_padre == subcat_padre_obj.id_subcategoria,
                             Subcategoria.id_categoria_contenedora == cat_principal_obj.id_categoria) # O la cat_contenedora del padre
    else: # No se especificó padre claro, no se puede crear/buscar de forma segura
        print(f"Advertencia: No se puede crear/buscar subcategoría '{nombre_subcat}' sin una Categoria Principal o Subcategoria Padre definida.")
        return None
        
    subcategoria = query.first()

    if not subcategoria:
        print(f"Creando nueva subcategoría: '{nombre_subcat}'")
        subcategoria = Subcategoria(
            nombre_subcategoria=nombre_subcat,
            id_categoria_contenedora=cat_principal_obj.id_categoria if cat_principal_obj else (subcat_padre_obj.id_categoria_contenedora if subcat_padre_obj else None),
            id_subcategoria_padre=subcat_padre_obj.id_subcategoria if subcat_padre_obj else None
        )
        db.add(subcategoria)
        try:
            db.flush()
        except Exception as e_flush_sub:
            db.rollback()
            print(f"Error al crear subcategoría '{nombre_subcat}': {e_flush_sub}")
            return None
    return subcategoria


def generar_siguiente_sku(db: Session, categoria_base_para_sku: Categoria) -> str | None:
    """
    Genera el siguiente SKU para una categoría dada que DEBE tener un prefijo_sku.
    """
    if not categoria_base_para_sku or not categoria_base_para_sku.prefijo_sku:
        nombre_cat = categoria_base_para_sku.nombre_categoria if categoria_base_para_sku else "Desconocida"
        print(f"Error: La categoría base '{nombre_cat}' para SKU no tiene un prefijo SKU definido.")
        return None
    
    # Usar with_for_update para bloquear la fila del contador durante la transacción
    contador = db.query(ContadorSKU).filter(
        ContadorSKU.id_categoria == categoria_base_para_sku.id_categoria
    ).with_for_update().first()
    
    if not contador:
        print(f"Advertencia: No se encontró contador SKU para la categoría ID {categoria_base_para_sku.id_categoria} ('{categoria_base_para_sku.nombre_categoria}'). Creando uno.")
        contador = ContadorSKU(id_categoria=categoria_base_para_sku.id_categoria, ultimo_valor=0)
        db.add(contador)
        try:
            db.flush() # Para asegurar que el contador se cree antes de incrementar
        except Exception as e_flush_cont:
            db.rollback()
            print(f"Error al crear contador para categoría '{categoria_base_para_sku.nombre_categoria}': {e_flush_cont}")
            return None

    contador.ultimo_valor += 1
    # db.flush() # El flush se hará como parte del commit general de la sesión
    numero_secuencial = str(contador.ultimo_valor).zfill(5)
    return f"{categoria_base_para_sku.prefijo_sku}-{numero_secuencial}"


def construir_descripcion_completa(prod_data: dict) -> str:
    """
    Construye una descripción completa del producto basada en sus atributos.
    Adaptada para los nuevos nombres de campo del modelo Producto (v3).
    """
    partes = [
        prod_data.get("nombre_producto", ""),
        prod_data.get("sabor", ""),
        prod_data.get("color", ""),
        prod_data.get("material", ""),
        prod_data.get("tamano_pulgadas", ""),
        prod_data.get("dimensiones_capacidad", ""),
        prod_data.get("tema_estilo", ""),
        prod_data.get("forma_tipo", ""),
        prod_data.get("presentacion_compra", ""), # Usar presentacion_compra
        # cantidad_en_presentacion_compra y unidad_medida_base podrían ser muy técnicos para la descripción completa
        # prod_data.get("cantidad_en_presentacion_compra", ""), 
        # prod_data.get("unidad_medida_base", "")
    ]
    # Filtrar valores None o vacíos y luego unir. Asegurarse que todos sean strings.
    descripcion = " ".join(filter(None, [str(p).strip() if p is not None else '' for p in partes])).strip()
    return " ".join(descripcion.split()) # Remover espacios múltiples


# --- Funciones Principales de Carga de Productos Internos desde CSV ---

def parsear_y_validar_csv_productos(stream_archivo_csv):
    """
    Parsea y valida un archivo CSV para la carga masiva de productos internos.
    Adaptado para la nueva estructura de CSV y modelos (v3).
    """
    productos_para_cargar = []
    errores_filas = []
    line_number_for_error_reporting = 1 # El encabezado es la fila 1

    try:
        # Decodificar el stream y manejar el BOM
        decoded_lines = [line.decode('utf-8-sig').rstrip('\r\n') for line in stream_archivo_csv]
        if not decoded_lines:
            return {"productos_listos": [], "errores": [{"fila": 1, "error": "Archivo CSV vacío.", "datos": {}}]}

        reader = csv.DictReader(decoded_lines)

        if not reader.fieldnames:
            return {"productos_listos": [], "errores": [{"fila": 1, "error": "No se pudieron leer los encabezados del CSV.", "datos": {}}]}

        # Columnas esperadas según `cargar_productos_html_v2`
        expected_fieldnames = [
            "NombreProducto", "UnidadMedidaBase", "CategoriaPrincipal", "SubcategoriaEspecifica", 
            "SubcategoriaPadre", "PresentacionCompra", "CantidadEnPresentacionCompra", 
            "DiasAnticipacionCompraProveedor", "DescripcionAdicional", "Sabor", "Color", 
            "TamanoPulgadas", "Material", "DimensionesCapacidad", "TemaEstilo", "FormaTipo", 
            "ModalidadServicioDirecto"
        ]
        # Verificar que al menos las obligatorias estén. Las demás son opcionales.
        obligatorias_csv = ["NombreProducto", "UnidadMedidaBase"]
        missing_headers = [h for h in obligatorias_csv if h not in reader.fieldnames]
        if missing_headers:
            errores_filas.append({"fila": 1, "error": f"Faltan encabezados obligatorios en el CSV: {', '.join(missing_headers)}", "datos": {"encabezados_detectados": reader.fieldnames}})
            return {"productos_listos": [], "errores": errores_filas}

        for row_data_raw in reader:
            line_number_for_error_reporting += 1
            row_data = {key.strip(): str(value).strip() if value is not None else '' for key, value in row_data_raw.items()}
            
            errores_esta_fila = []

            # 1. Validar campos siempre obligatorios del CSV
            nombre_producto_csv = row_data.get('NombreProducto')
            unidad_medida_base_csv = row_data.get('UnidadMedidaBase')

            if not nombre_producto_csv:
                errores_esta_fila.append("Falta valor para columna obligatoria 'NombreProducto'.")
            if not unidad_medida_base_csv:
                errores_esta_fila.append("Falta valor para columna obligatoria 'UnidadMedidaBase'.")

            # 2. Validar categorización (al menos una forma debe estar presente)
            cat_principal_csv = row_data.get('CategoriaPrincipal')
            subcat_especifica_csv = row_data.get('SubcategoriaEspecifica')
            # SubcategoriaPadre solo es relevante si SubcategoriaEspecifica está presente
            if not cat_principal_csv and not subcat_especifica_csv:
                errores_esta_fila.append("Debe especificarse 'CategoriaPrincipal' o 'SubcategoriaEspecifica'.")

            # 3. Validar campos numéricos opcionales si están presentes
            cantidad_presentacion_str = row_data.get('CantidadEnPresentacionCompra')
            cantidad_presentacion_val = None
            if cantidad_presentacion_str:
                try:
                    cantidad_presentacion_val = Decimal(cantidad_presentacion_str)
                    if cantidad_presentacion_val < 0:
                        errores_esta_fila.append("'CantidadEnPresentacionCompra' no puede ser negativa.")
                except InvalidOperation:
                    errores_esta_fila.append(f"Valor no numérico para 'CantidadEnPresentacionCompra': '{cantidad_presentacion_str}'.")
            
            dias_anticipacion_str = row_data.get('DiasAnticipacionCompraProveedor')
            dias_anticipacion_val = None
            if dias_anticipacion_str:
                if dias_anticipacion_str.isdigit():
                    dias_anticipacion_val = int(dias_anticipacion_str)
                    if dias_anticipacion_val < 0:
                        errores_esta_fila.append("'DiasAnticipacionCompraProveedor' no puede ser negativo.")
                else:
                    errores_esta_fila.append(f"Valor no numérico para 'DiasAnticipacionCompraProveedor': '{dias_anticipacion_str}'.")

            if errores_esta_fila:
                errores_filas.append({"fila": line_number_for_error_reporting, "error": "; ".join(errores_esta_fila), "datos": row_data_raw})
                continue # Saltar al siguiente producto si hay errores fundamentales

            # Si pasa validaciones, preparar datos para guardar
            producto_info = {
                "nombre_producto": nombre_producto_csv,
                "unidad_medida_base": unidad_medida_base_csv,
                "csv_categoria_principal": cat_principal_csv,
                "csv_subcategoria_especifica": subcat_especifica_csv,
                "csv_subcategoria_padre": row_data.get('SubcategoriaPadre'), # Puede estar vacío
                "presentacion_compra": row_data.get('PresentacionCompra'),
                "cantidad_en_presentacion_compra": cantidad_presentacion_val,
                "dias_anticipacion_compra_proveedor": dias_anticipacion_val,
                "descripcion_adicional": row_data.get('DescripcionAdicional'),
                "sabor": row_data.get('Sabor'),
                "color": row_data.get('Color'),
                "tamano_pulgadas": row_data.get('TamanoPulgadas'),
                "material": row_data.get('Material'),
                "dimensiones_capacidad": row_data.get('DimensionesCapacidad'),
                "tema_estilo": row_data.get('TemaEstilo'),
                "forma_tipo": row_data.get('FormaTipo'),
                "modalidad_servicio_directo": row_data.get('ModalidadServicioDirecto'),
                "activo": True # Por defecto, los productos cargados están activos
            }
            productos_para_cargar.append(producto_info)

        return {"productos_listos": productos_para_cargar, "errores": errores_filas}

    except csv.Error as e_csv:
        print(f"Error de formato CSV: {str(e_csv)}")
        return {"productos_listos": [], "errores": [{"fila": line_number_for_error_reporting, "error": f"Error de formato en el archivo CSV: {str(e_csv)}", "datos": {}}]}
    except Exception as e_file:
        print(f"Error al parsear el stream del CSV: {str(e_file)}")
        return {"productos_listos": [], "errores": [{"fila": 1, "error": f"Error general al leer el archivo: {str(e_file)}", "datos": {}}]}


def guardar_productos_en_bd(db: Session, productos_a_guardar: list):
    """
    Guarda los productos parseados en la base de datos.
    Adaptado para la nueva estructura de modelos y categorización jerárquica (v3).
    """
    productos_guardados_count = 0
    productos_omitidos_count = 0 # Por SKU duplicado o error de categorización
    errores_guardado_detalle = []

    if not productos_a_guardar:
        return {"mensaje": "No hay productos válidos para guardar.", "guardados": 0, "omitidos": 0, "errores_detalle_guardado": []}

    for prod_data_csv in productos_a_guardar:
        try:
            # 1. Determinar Categorización
            cat_principal_obj = None
            subcat_especifica_obj = None
            subcat_padre_obj = None # Para buscar la subcategoría específica

            nombre_cat_principal_csv = prod_data_csv.get("csv_categoria_principal")
            nombre_subcat_especifica_csv = prod_data_csv.get("csv_subcategoria_especifica")
            nombre_subcat_padre_csv = prod_data_csv.get("csv_subcategoria_padre")

            if nombre_cat_principal_csv:
                cat_principal_obj = get_or_create_categoria_principal(db, nombre_cat_principal_csv)
                if not cat_principal_obj:
                    errores_guardado_detalle.append(f"Producto '{prod_data_csv['nombre_producto']}': No se pudo obtener/crear Categoría Principal '{nombre_cat_principal_csv}'. Omitido.")
                    productos_omitidos_count += 1
                    db.rollback() # Revertir cualquier creación parcial de categoría
                    continue
            
            if nombre_subcat_padre_csv: # Si se especifica un padre para la subcategoría específica
                # Primero, asegurar que la subcategoría padre exista (puede estar bajo cat_principal_obj o ser independiente si cat_principal_obj es None)
                # Esta lógica puede necesitar ser más robusta para encontrar subcat_padre_obj en una jerarquía.
                # Por ahora, asumimos que si se da subcat_padre_csv, también se da cat_principal_csv para su raíz, o que subcat_padre_csv es única.
                subcat_padre_obj = db.query(Subcategoria).filter(Subcategoria.nombre_subcategoria == nombre_subcat_padre_csv).first()
                if not subcat_padre_obj:
                     # Intentar crearla si tiene una categoría principal asociada
                    if cat_principal_obj:
                        subcat_padre_obj = get_or_create_subcategoria_anidada(db, nombre_subcat_padre_csv, cat_principal_obj=cat_principal_obj)
                    if not subcat_padre_obj:
                        errores_guardado_detalle.append(f"Producto '{prod_data_csv['nombre_producto']}': Subcategoría Padre '{nombre_subcat_padre_csv}' no encontrada/creada. Omitido.")
                        productos_omitidos_count += 1
                        db.rollback()
                        continue
            
            if nombre_subcat_especifica_csv:
                # La subcategoría específica puede estar bajo cat_principal_obj o subcat_padre_obj
                if subcat_padre_obj: # Priorizar que esté bajo la subcategoría padre si se especificó
                    subcat_especifica_obj = get_or_create_subcategoria_anidada(db, nombre_subcat_especifica_csv, subcat_padre_obj=subcat_padre_obj)
                elif cat_principal_obj: # Si no hay subcat_padre, pero sí cat_principal
                    subcat_especifica_obj = get_or_create_subcategoria_anidada(db, nombre_subcat_especifica_csv, cat_principal_obj=cat_principal_obj)
                
                if not subcat_especifica_obj:
                    errores_guardado_detalle.append(f"Producto '{prod_data_csv['nombre_producto']}': No se pudo obtener/crear Subcategoría Específica '{nombre_subcat_especifica_csv}'. Omitido.")
                    productos_omitidos_count += 1
                    db.rollback()
                    continue
            
            # 2. Determinar Categoría Base para SKU
            categoria_para_sku = None
            if cat_principal_obj and cat_principal_obj.prefijo_sku:
                categoria_para_sku = cat_principal_obj
            elif subcat_especifica_obj: # Intentar obtenerla de la jerarquía de la subcategoría
                current_ancestor = subcat_especifica_obj.categoria_contenedora
                while current_ancestor:
                    if current_ancestor.prefijo_sku:
                        categoria_para_sku = current_ancestor
                        break
                    current_ancestor = current_ancestor.categoria_padre # Asumiendo que Categoria tiene esta relación
            
            if not categoria_para_sku:
                errores_guardado_detalle.append(f"Producto '{prod_data_csv['nombre_producto']}': No se pudo determinar una categoría con prefijo SKU. Omitido.")
                productos_omitidos_count += 1
                db.rollback()
                continue

            # 3. Generar SKU
            nuevo_sku = generar_siguiente_sku(db, categoria_para_sku)
            if not nuevo_sku:
                errores_guardado_detalle.append(f"Producto '{prod_data_csv['nombre_producto']}': No se pudo generar SKU. Omitido.")
                productos_omitidos_count += 1
                db.rollback()
                continue
            
            # Verificar si el SKU ya existe (aunque generar_siguiente_sku debería ser robusto si la sesión es la misma)
            producto_existente_sku = db.query(Producto).filter(Producto.sku == nuevo_sku).first()
            if producto_existente_sku:
                errores_guardado_detalle.append(f"Producto '{prod_data_csv['nombre_producto']}': SKU generado '{nuevo_sku}' ya existe. Omitido.")
                productos_omitidos_count += 1
                db.rollback() # Revertir el incremento del contador SKU si es posible (difícil si no es la misma transacción)
                # O mejor, no hacer rollback aquí y solo omitir, el contador ya incrementó.
                continue

            # 4. Preparar datos para el modelo Producto
            datos_modelo_producto = {
                "nombre_producto": prod_data_csv["nombre_producto"],
                "sku": nuevo_sku,
                "id_categoria_principal_producto": cat_principal_obj.id_categoria if cat_principal_obj else None,
                "id_subcategoria_especifica_producto": subcat_especifica_obj.id_subcategoria if subcat_especifica_obj else None,
                "unidad_medida_base": prod_data_csv["unidad_medida_base"],
                "activo": prod_data_csv.get("activo", True)
            }
            
            # Campos opcionales del Producto
            opcionales_producto = [
                "descripcion_adicional", "presentacion_compra", "cantidad_en_presentacion_compra",
                "dias_anticipacion_compra_proveedor", "sabor", "color", "tamano_pulgadas",
                "material", "dimensiones_capacidad", "tema_estilo", "forma_tipo", "modalidad_servicio_directo"
            ]
            for campo in opcionales_producto:
                if prod_data_csv.get(campo) is not None and str(prod_data_csv.get(campo)).strip() != '':
                    datos_modelo_producto[campo] = prod_data_csv[campo]
            
            datos_modelo_producto["descripcion_completa_generada"] = construir_descripcion_completa(datos_modelo_producto)
            
            nuevo_producto_obj = Producto(**datos_modelo_producto)
            db.add(nuevo_producto_obj)
            
            # No hacer commit aquí, hacerlo al final para todos los productos válidos.
            productos_guardados_count += 1

        except Exception as e_save:
            db.rollback() # Revertir cambios para este producto específico
            errores_guardado_detalle.append(f"Error inesperado al procesar '{prod_data_csv.get('nombre_producto', 'Desconocido')}': {str(e_save)}. Omitido.")
            productos_omitidos_count += 1
            continue # Continuar con el siguiente producto

    try:
        if productos_guardados_count > 0:
            db.commit() # Commit final para todos los productos guardados exitosamente
    except Exception as e_commit:
        # Si el commit final falla, todos los productos de este lote fallan.
        # Esto es un escenario problemático, ya que los contadores SKU podrían haber incrementado.
        db.rollback()
        errores_guardado_detalle.append(f"Error crítico al hacer commit final a la BD: {str(e_commit)}. Todos los productos de este lote fueron revertidos.")
        # Resetear contadores si el commit falla (esto es complejo y puede requerir lógica adicional)
        productos_guardados_count = 0 # Ninguno se guardó realmente

    mensaje_final = f"Proceso de carga de productos finalizado. Productos nuevos guardados: {productos_guardados_count}. Omitidos/Errores: {productos_omitidos_count}."
    
    return {
        "mensaje": mensaje_final,
        "guardados": productos_guardados_count,
        "omitidos": productos_omitidos_count,
        "errores_detalle_guardado": errores_guardado_detalle
    }


# --- Funciones para Carga de Precios (se mantienen por ahora, revisar si necesitan adaptación) ---
# parsear_y_validar_csv_precios
# guardar_precios_en_bd
# ... (Tu código existente para parsear y guardar precios de proveedor va aquí) ...
# Deberás asegurarte de que estas funciones importen Proveedor y PrecioProveedor si no lo hacen ya.
# Y que la forma de identificar Producto (ej. por SKU) siga siendo válida.

# Placeholder para las funciones de precios si no las tienes en este archivo:
def parsear_y_validar_csv_precios(db: Session, stream_archivo_csv):
    # Implementación para parsear CSV de precios
    print("Advertencia: parsear_y_validar_csv_precios no está completamente implementado con los nuevos modelos.")
    return {"precios_listos": [], "errores": [{"fila":1, "error": "Función no implementada"}]}

def guardar_precios_en_bd(db: Session, precios_a_procesar: list):
    # Implementación para guardar precios
    print("Advertencia: guardar_precios_en_bd no está completamente implementado con los nuevos modelos.")
    return {"mensaje": "Función no implementada"}

