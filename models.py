# models.py
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DECIMAL, Date, TIMESTAMP, func, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from decimal import Decimal, InvalidOperation


Base = declarative_base()

# --- MODELOS DE CATEGORIZACIÓN DE PRODUCTOS INTERNOS ---
class Categoria(Base):
    __tablename__ = 'categorias'
    id_categoria = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_categoria = Column(String(100), unique=True, nullable=False, index=True)
    prefijo_sku = Column(String(5), unique=True, nullable=True, index=True)
    id_categoria_padre = Column(Integer, ForeignKey('categorias.id_categoria'), nullable=True)
    
    subcategorias_directas = relationship("Subcategoria", foreign_keys="[Subcategoria.id_categoria_contenedora]", back_populates="categoria_contenedora")
    categoria_padre = relationship("Categoria", remote_side=[id_categoria], back_populates="categorias_hijas")
    categorias_hijas = relationship("Categoria", back_populates="categoria_padre")
    productos_en_categoria = relationship("Producto", foreign_keys="[Producto.id_categoria_principal_producto]", back_populates="categoria_principal_producto")
    contadores_sku = relationship("ContadorSKU", back_populates="categoria_contador")

    def __repr__(self):
        return f"<Categoria(id={self.id_categoria}, nombre='{self.nombre_categoria}')>"

class Subcategoria(Base):
    __tablename__ = 'subcategorias'
    id_subcategoria = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_subcategoria = Column(String(100), nullable=False, index=True)
    id_categoria_contenedora = Column(Integer, ForeignKey('categorias.id_categoria'), nullable=True)
    id_subcategoria_padre = Column(Integer, ForeignKey('subcategorias.id_subcategoria'), nullable=True)
    
    categoria_contenedora = relationship("Categoria", foreign_keys=[id_categoria_contenedora], back_populates="subcategorias_directas")
    subcategoria_padre_ref = relationship("Subcategoria", remote_side=[id_subcategoria], back_populates="subcategorias_hijas_directas") 
    subcategorias_hijas_directas = relationship("Subcategoria", back_populates="subcategoria_padre_ref")
    productos_en_subcategoria = relationship("Producto", foreign_keys="[Producto.id_subcategoria_especifica_producto]", back_populates="subcategoria_especifica_producto")

    def __repr__(self):
        return f"<Subcategoria(id={self.id_subcategoria}, nombre='{self.nombre_subcategoria}')>"

class Producto(Base):
    __tablename__ = 'productos'
    id_producto = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_producto = Column(String(255), nullable=False, index=True)
    id_categoria_principal_producto = Column(Integer, ForeignKey('categorias.id_categoria'), nullable=True)
    id_subcategoria_especifica_producto = Column(Integer, ForeignKey('subcategorias.id_subcategoria'), nullable=True)
    sku = Column(String(50), unique=True, nullable=True, index=True)
    descripcion_adicional = Column(Text, nullable=True)
    descripcion_completa_generada = Column(Text, nullable=True)
    presentacion_compra = Column(String(100), nullable=True) 
    cantidad_en_presentacion_compra = Column(DECIMAL(10,3), nullable=True) 
    unidad_medida_base = Column(String(50), nullable=False)
    es_indivisible = Column(Boolean, default=False, nullable=False)
    sabor = Column(String(100), nullable=True)
    color = Column(String(100), nullable=True)
    tamano_pulgadas = Column(String(50), nullable=True) 
    material = Column(String(100), nullable=True)
    dimensiones_capacidad = Column(String(100), nullable=True)
    tema_estilo = Column(String(100), nullable=True)
    modalidad_servicio_directo = Column(String(100), nullable=True) 
    forma_tipo = Column(String(100), nullable=True)
    dias_anticipacion_compra_proveedor = Column(Integer, nullable=True)
    marca = Column(String(100), nullable=True) 
    modelo_sku_proveedor = Column(String(100), nullable=True) 
    activo = Column(Boolean, default=True, nullable=False)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())
    fecha_actualizacion = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    categoria_principal_producto = relationship("Categoria", foreign_keys=[id_categoria_principal_producto], back_populates="productos_en_categoria")
    subcategoria_especifica_producto = relationship("Subcategoria", foreign_keys=[id_subcategoria_especifica_producto], back_populates="productos_en_subcategoria")
    precios_proveedor = relationship("PrecioProveedor", back_populates="producto", cascade="all, delete-orphan")
    detalles_compra = relationship("DetalleCompra", back_populates="producto", cascade="all, delete-orphan")
    opciones_componente_servicio = relationship("OpcionComponenteServicio", back_populates="producto_interno_ref")

    existencias = relationship("ExistenciaProducto", back_populates="producto", cascade="all, delete-orphan")
    movimientos_inventario = relationship("MovimientoInventario", back_populates="producto", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Producto(id={self.id_producto}, nombre='{self.nombre_producto}', sku='{self.sku}')>"

class Proveedor(Base):
    __tablename__ = 'proveedores'
    id_proveedor = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_proveedor = Column(String(150), nullable=False, index=True)
    activo = Column(Boolean, default=True, nullable=False)
    precios = relationship("PrecioProveedor", back_populates="proveedor", cascade="all, delete-orphan")
    encabezados_compra = relationship("EncabezadoCompra", back_populates="proveedor", cascade="all, delete-orphan")
    contacto_nombre = Column(String(150), nullable=True)
    telefono = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    direccion = Column(Text, nullable=True)
    notas = Column(Text, nullable=True)
    rfc = Column(String(13), nullable=True, index=True)
    razon_social = Column(String(255), nullable=True)
    regimen_fiscal = Column(String(255), nullable=True)
    codigo_postal_fiscal = Column(String(10), nullable=True)
    email_facturacion = Column(String(100), nullable=True)
    def __repr__(self): return f"<Proveedor(id={self.id_proveedor}, nombre='{self.nombre_proveedor}')>"

class PrecioProveedor(Base):
    __tablename__ = 'precios_proveedores'
    id_precio_proveedor = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_producto = Column(Integer, ForeignKey('productos.id_producto', ondelete="CASCADE"), nullable=False)
    id_proveedor = Column(Integer, ForeignKey('proveedores.id_proveedor', ondelete="CASCADE"), nullable=False)
    precio_compra = Column(DECIMAL(10, 2), nullable=False) 
    unidad_compra_proveedor = Column(String(50), nullable=True) 
    cantidad_minima_compra = Column(Integer, nullable=True) 
    fecha_actualizacion_precio = Column(Date, nullable=False, default=func.today())
    notas = Column(Text, nullable=True)
    producto = relationship("Producto", back_populates="precios_proveedor")
    proveedor = relationship("Proveedor", back_populates="precios")
    def __repr__(self): return f"<PrecioProveedor(prod_id={self.id_producto}, prov_id={self.id_proveedor}, precio={self.precio_compra})>"

class ContadorSKU(Base):
    __tablename__ = 'contadores_sku'
    id_categoria = Column(Integer, ForeignKey('categorias.id_categoria'), primary_key=True)
    ultimo_valor = Column(Integer, nullable=False, default=0)
    categoria_contador = relationship("Categoria", back_populates="contadores_sku")
    def __repr__(self): return f"<ContadorSKU(id_cat={self.id_categoria}, val={self.ultimo_valor})>"

class EncabezadoCompra(Base):
    __tablename__ = 'encabezados_compra'
    id_encabezado_compra = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_proveedor = Column(Integer, ForeignKey('proveedores.id_proveedor'), nullable=False)
    fecha_documento = Column(Date, nullable=False, default=func.today())
    numero_documento = Column(String(100), nullable=True, index=True)
    monto_total_documento = Column(DECIMAL(12, 2), nullable=True)
    notas_generales = Column(Text, nullable=True)
    fecha_registro_sistema = Column(TIMESTAMP, server_default=func.now())
    proveedor = relationship("Proveedor", back_populates="encabezados_compra")
    detalles = relationship("DetalleCompra", back_populates="encabezado", cascade="all, delete-orphan")
    def __repr__(self): return f"<EncabezadoCompra(id={self.id_encabezado_compra}, num_doc='{self.numero_documento}')>"

class DetalleCompra(Base):
    __tablename__ = 'detalles_compra'
    id_detalle_compra = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_encabezado_compra = Column(Integer, ForeignKey('encabezados_compra.id_encabezado_compra'), nullable=False)
    id_producto = Column(Integer, ForeignKey('productos.id_producto'), nullable=False)
    cantidad_comprada = Column(DECIMAL(10,2), nullable=False) 
    unidad_compra = Column(String(100), nullable=False) 
    precio_original_unitario = Column(DECIMAL(10, 2), nullable=True)
    monto_descuento_unitario = Column(DECIMAL(10, 2), nullable=True, default=0.00)
    costo_unitario_compra = Column(DECIMAL(10, 2), nullable=False)
    costo_total_item = Column(DECIMAL(12, 2), nullable=False)
    disponibilidad_proveedor = Column(String(50), nullable=True) 
    notas_item = Column(Text, nullable=True)
    encabezado = relationship("EncabezadoCompra", back_populates="detalles")
    producto = relationship("Producto", back_populates="detalles_compra")
    def __repr__(self): return f"<DetalleCompra(id={self.id_detalle_compra}, prod_id={self.id_producto})>"

class TipoServicioBase(Base):
    __tablename__ = 'tipos_servicio_base'
    id_tipo_servicio_base = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(150), unique=True, nullable=False, index=True) 
    descripcion = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)
    variantes_servicio = relationship("VarianteServicioConfig", back_populates="tipo_servicio_base_ref")
    def __repr__(self): return f"<TipoServicioBase(nombre='{self.nombre}')>"

class VarianteServicioConfig(Base):
    __tablename__ = 'variantes_servicio_config'
    id_variante_config = Column(Integer, primary_key=True, autoincrement=True)
    id_tipo_servicio_base = Column(Integer, ForeignKey('tipos_servicio_base.id_tipo_servicio_base'), nullable=False)
    nombre_variante = Column(String(255), nullable=False, index=True) 
    nivel_paquete = Column(String(100), nullable=True, index=True) 
    nivel_perfil = Column(String(100), nullable=True, index=True)  
    codigo_identificador_variante = Column(String(50), unique=True, nullable=True, index=True) 
    descripcion_publica = Column(Text, nullable=True)
    precio_base_sugerido = Column(DECIMAL(10,2), nullable=True)
    activo = Column(Boolean, default=True)
    cantidad_base_por_invitado = Column(DECIMAL(10,3), nullable=True)
    unidad_medida_servicio_por_invitado = Column(String(50), nullable=True)
    cantidad_base_fija_servicio = Column(DECIMAL(10,2), nullable=True)
    tipo_servicio_base_ref = relationship("TipoServicioBase", back_populates="variantes_servicio")
    grupos_componentes = relationship("GrupoComponenteConfig", back_populates="variante_servicio_config_ref", cascade="all, delete-orphan")
    items_cotizacion_asociados = relationship("ItemCotizacion", back_populates="variante_servicio_config_usada")
    def __repr__(self): return f"<VarianteServicioConfig(nombre='{self.nombre_variante}', paquete='{self.nivel_paquete}', perfil='{self.nivel_perfil}')>"

class GrupoComponenteConfig(Base):
    __tablename__ = 'grupos_componente_config'
    id_grupo_config = Column(Integer, primary_key=True, autoincrement=True)
    id_variante_config = Column(Integer, ForeignKey('variantes_servicio_config.id_variante_config'), nullable=False)
    nombre_grupo = Column(String(150), nullable=False) 
    cantidad_opciones_seleccionables = Column(Integer, nullable=False, default=1)
    porcentaje_del_total_servicio = Column(DECIMAL(5,2), nullable=True) 
    orden_display = Column(Integer, default=0)
    variante_servicio_config_ref = relationship("VarianteServicioConfig", back_populates="grupos_componentes")
    opciones_componente_disponibles = relationship("OpcionComponenteServicio", back_populates="grupo_componente_config_ref", cascade="all, delete-orphan")
    def __repr__(self): return f"<GrupoComponenteConfig(nombre='{self.nombre_grupo}')>"

class OpcionComponenteServicio(Base):
    __tablename__ = 'opciones_componente_servicio'
    id_opcion_componente = Column(Integer, primary_key=True, autoincrement=True)
    id_grupo_config = Column(Integer, ForeignKey('grupos_componente_config.id_grupo_config'), nullable=False)
    id_producto_interno = Column(Integer, ForeignKey('productos.id_producto'), nullable=True) 
    nombre_display_cliente = Column(String(200), nullable=False)
    descripcion_display_cliente = Column(Text, nullable=True)
    cantidad_consumo_base = Column(DECIMAL(10,3), nullable=False)
    unidad_consumo_base = Column(String(50), nullable=False)
    costo_adicional_opcion = Column(DECIMAL(10,2), default=0.00)
    precio_venta_opcion_sugerido = Column(DECIMAL(10,2), nullable=True)
    activo = Column(Boolean, default=True)
    grupo_componente_config_ref = relationship("GrupoComponenteConfig", back_populates="opciones_componente_disponibles")
    producto_interno_ref = relationship("Producto", back_populates="opciones_componente_servicio")
    selecciones_en_cotizaciones = relationship("DetalleComponenteSeleccionado", back_populates="opcion_componente_elegida")
    def __repr__(self): return f"<OpcionComponenteServicio(nombre_cliente='{self.nombre_display_cliente}')>"

class Proyecto(Base):
    __tablename__ = 'proyectos'
    id_proyecto = Column(Integer, primary_key=True, autoincrement=True)
    identificador_evento = Column(String(150), unique=True, nullable=False, index=True)
    nombre_evento = Column(String(255), nullable=False)
    fecha_evento = Column(Date, nullable=False)
    numero_invitados = Column(Integer, nullable=True, default=1)
    cliente_nombre = Column(String(255), nullable=True)
    cliente_telefono = Column(String(50), nullable=True)
    cliente_email = Column(String(100), nullable=True)
    direccion_evento = Column(Text, nullable=True)
    tipo_ubicacion = Column(String(100), default='Local (CDMX y Área Metropolitana)', nullable=False)
    costo_transporte_estimado = Column(DECIMAL(10,2), nullable=True, default=0.00)
    costo_viaticos_estimado = Column(DECIMAL(10,2), nullable=True, default=0.00)
    costo_hospedaje_estimado = Column(DECIMAL(10,2), nullable=True, default=0.00)
    notas_proyecto = Column(Text, nullable=True)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())
    fecha_actualizacion = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    cotizaciones = relationship("Cotizacion", back_populates="proyecto", cascade="all, delete-orphan")
    def __repr__(self): return f"<Proyecto(evento='{self.nombre_evento}')>"

class Cotizacion(Base):
    __tablename__ = 'cotizaciones'
    id_cotizacion = Column(Integer, primary_key=True, autoincrement=True)
    id_proyecto = Column(Integer, ForeignKey('proyectos.id_proyecto'), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    fecha_emision = Column(Date, nullable=False, default=func.today())
    fecha_validez = Column(Date, nullable=True)
    estado = Column(String(50), nullable=False, default="Borrador", index=True)
    numero_invitados_override = Column(Integer, nullable=True) 
    monto_servicios_productos = Column(DECIMAL(12, 2), nullable=True, default=0.00)
    monto_costos_logisticos = Column(DECIMAL(12, 2), nullable=True, default=0.00)
    monto_subtotal_general = Column(DECIMAL(12, 2), nullable=True, default=0.00)
    
    # Campos para almacenar los montos calculados
    monto_descuento_global = Column(DECIMAL(12,2), nullable=True, default=0.00)
    monto_impuestos = Column(DECIMAL(12, 2), nullable=True, default=0.00)
    
    # NUEVOS CAMPOS PARA PORCENTAJES
    porcentaje_descuento_global = Column(DECIMAL(5,2), nullable=True) # Ej. 10.00 para 10%
    porcentaje_impuestos = Column(DECIMAL(5,2), nullable=True)      # Ej. 16.00 para 16%

    monto_total_cotizado = Column(DECIMAL(12, 2), nullable=True, default=0.00)
    terminos_condiciones = Column(Text, nullable=True)
    notas_cotizacion = Column(Text, nullable=True)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())
    fecha_actualizacion = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    proyecto = relationship("Proyecto", back_populates="cotizaciones")
    items_cotizacion = relationship("ItemCotizacion", back_populates="cotizacion_ref", cascade="all, delete-orphan")
    def __repr__(self): return f"<Cotizacion(id={self.id_cotizacion}, proyecto_id={self.id_proyecto})>"

class ItemCotizacion(Base):
    __tablename__ = 'items_cotizacion'
    id_item_cotizacion = Column(Integer, primary_key=True, autoincrement=True)
    id_cotizacion = Column(Integer, ForeignKey('cotizaciones.id_cotizacion'), nullable=False)
    id_variante_servicio_config = Column(Integer, ForeignKey('variantes_servicio_config.id_variante_config'), nullable=True) 
    nombre_display_servicio = Column(String(255), nullable=False)
    descripcion_servicio_cotizado = Column(Text, nullable=True)
    cantidad_servicio = Column(DECIMAL(10,2), nullable=False, default=1)
    precio_total_item_calculado = Column(DECIMAL(10, 2), nullable=False)
    notas_item_cot = Column(Text, nullable=True)
    orden_display_cot = Column(Integer, default=0)
    numero_invitados_servicio_item = Column(Integer, nullable=True)

    cotizacion_ref = relationship("Cotizacion", back_populates="items_cotizacion")
    variante_servicio_config_usada = relationship("VarianteServicioConfig", back_populates="items_cotizacion_asociados")
    componentes_seleccionados = relationship("DetalleComponenteSeleccionado", back_populates="item_cotizacion_pertenece", cascade="all, delete-orphan")
    def __repr__(self): return f"<ItemCotizacion(nombre='{self.nombre_display_servicio}')>"

class DetalleComponenteSeleccionado(Base):
    __tablename__ = 'detalles_componente_seleccionado'
    id_detalle_seleccion = Column(Integer, primary_key=True, autoincrement=True)
    id_item_cotizacion = Column(Integer, ForeignKey('items_cotizacion.id_item_cotizacion'), nullable=False)
    id_opcion_componente = Column(Integer, ForeignKey('opciones_componente_servicio.id_opcion_componente'), nullable=False)
    cantidad_opcion_solicitada_cliente = Column(DECIMAL(10,2), nullable=False, default=1)
    cantidad_final_producto_interno_calc = Column(DECIMAL(10,3), nullable=True) 
    precio_venta_seleccion_cliente_calc = Column(DECIMAL(10,2), nullable=False) 
    notas_seleccion = Column(Text, nullable=True)
    item_cotizacion_pertenece = relationship("ItemCotizacion", back_populates="componentes_seleccionados")
    opcion_componente_elegida = relationship("OpcionComponenteServicio", back_populates="selecciones_en_cotizaciones")
    def __repr__(self): return f"<DetalleComponenteSeleccionado(opcion_id={self.id_opcion_componente})>"

class Almacen(Base):
    __tablename__ = 'almacenes'
    id_almacen = Column(Integer, primary_key=True, autoincrement=True)
    nombre_almacen = Column(String(150), unique=True, nullable=False, index=True)
    descripcion = Column(Text, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)

    existencias = relationship("ExistenciaProducto", back_populates="almacen", cascade="all, delete-orphan")
    movimientos_origen = relationship("MovimientoInventario", foreign_keys="[MovimientoInventario.id_almacen_origen]", back_populates="almacen_origen_rel", cascade="all, delete-orphan")
    movimientos_destino = relationship("MovimientoInventario", foreign_keys="[MovimientoInventario.id_almacen_destino]", back_populates="almacen_destino_rel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Almacen(id={self.id_almacen}, nombre='{self.nombre_almacen}')>"

class ExistenciaProducto(Base):
    __tablename__ = 'existencias_producto'
    id_existencia = Column(Integer, primary_key=True, autoincrement=True)
    id_producto = Column(Integer, ForeignKey('productos.id_producto', ondelete="CASCADE"), nullable=False, index=True)
    id_almacen = Column(Integer, ForeignKey('almacenes.id_almacen', ondelete="CASCADE"), nullable=False, index=True)
    
    cantidad_disponible = Column(DECIMAL(12, 3), nullable=False, default=Decimal('0.000'))
    cantidad_reservada = Column(DECIMAL(12, 3), nullable=False, default=Decimal('0.000'))
    
    @hybrid_property
    def cantidad_efectiva(self):
        return self.cantidad_disponible - self.cantidad_reservada

    punto_reorden = Column(DECIMAL(12, 3), nullable=True)
    stock_maximo_sugerido = Column(DECIMAL(12, 3), nullable=True)
    
    ultima_actualizacion = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    producto = relationship("Producto", back_populates="existencias")
    almacen = relationship("Almacen", back_populates="existencias")

    __table_args__ = (UniqueConstraint('id_producto', 'id_almacen', name='uq_producto_almacen_existencia'),)

    def __repr__(self):
        return f"<ExistenciaProducto(prod_id={self.id_producto}, alm_id={self.id_almacen}, disp={self.cantidad_disponible})>"

class MovimientoInventario(Base):
    __tablename__ = 'movimientos_inventario'
    id_movimiento = Column(Integer, primary_key=True, autoincrement=True)
    id_producto = Column(Integer, ForeignKey('productos.id_producto'), nullable=False, index=True)
    
    id_almacen_destino = Column(Integer, ForeignKey('almacenes.id_almacen'), nullable=True, index=True) 
    id_almacen_origen = Column(Integer, ForeignKey('almacenes.id_almacen'), nullable=True, index=True)

    tipo_movimiento = Column(String(50), nullable=False, index=True) 
    cantidad = Column(DECIMAL(12, 3), nullable=False)
    fecha_movimiento = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    id_documento_referencia = Column(Integer, nullable=True, index=True)
    tipo_documento_referencia = Column(String(50), nullable=True)
    
    costo_unitario_en_movimiento = Column(DECIMAL(10, 2), nullable=True)
    
    nombre_usuario_responsable = Column(String(150), nullable=True) 
    
    notas = Column(Text, nullable=True)

    producto = relationship("Producto", back_populates="movimientos_inventario")
    almacen_destino_rel = relationship("Almacen", foreign_keys=[id_almacen_destino], back_populates="movimientos_destino")
    almacen_origen_rel = relationship("Almacen", foreign_keys=[id_almacen_origen], back_populates="movimientos_origen")

    def __repr__(self):
        return f"<MovimientoInventario(id={self.id_movimiento}, prod_id={self.id_producto}, tipo='{self.tipo_movimiento}', cant={self.cantidad})>"
