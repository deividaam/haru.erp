# models.py
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DECIMAL, Date, TIMESTAMP, func
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Categoria(Base):
    __tablename__ = 'categorias'
    id_categoria = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_categoria = Column(String(100), unique=True, nullable=False, index=True)
    prefijo_sku = Column(String(5), unique=True, nullable=True, index=True)
    subcategorias = relationship("Subcategoria", back_populates="categoria")
    productos_directos = relationship("Producto", foreign_keys="[Producto.id_categoria_directa]", back_populates="categoria_directa")
    contadores_sku = relationship("ContadorSKU", back_populates="categoria")
    def __repr__(self):
        return f"<Categoria(id={self.id_categoria}, nombre='{self.nombre_categoria}')>"

class Subcategoria(Base):
    __tablename__ = 'subcategorias'
    id_subcategoria = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_subcategoria = Column(String(100), nullable=False, index=True)
    id_categoria = Column(Integer, ForeignKey('categorias.id_categoria'), nullable=False)
    categoria = relationship("Categoria", back_populates="subcategorias")
    productos = relationship("Producto", foreign_keys="[Producto.id_subcategoria]", back_populates="subcategoria")
    def __repr__(self):
        return f"<Subcategoria(id={self.id_subcategoria}, nombre='{self.nombre_subcategoria}')>"

class Producto(Base):
    __tablename__ = 'productos'
    id_producto = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_producto = Column(String(255), nullable=False, index=True)
    id_categoria_directa = Column(Integer, ForeignKey('categorias.id_categoria'), nullable=True)
    id_subcategoria = Column(Integer, ForeignKey('subcategorias.id_subcategoria'), nullable=True)
    sku = Column(String(50), unique=True, nullable=True, index=True)
    descripcion_adicional = Column(Text, nullable=True)
    descripcion_completa_generada = Column(Text, nullable=True)
    presentacion = Column(String(100), nullable=True) 
    cantidad_por_presentacion = Column(String(50), nullable=True)
    unidad_medida_venta = Column(String(50), nullable=True) 
    sabor = Column(String(100), nullable=True)
    color = Column(String(100), nullable=True)
    tamano_pulgadas = Column(String(50), nullable=True)
    material = Column(String(100), nullable=True)
    dimensiones_capacidad = Column(String(100), nullable=True)
    tema_estilo = Column(String(100), nullable=True)
    modalidad_servicio = Column(String(100), nullable=True)
    forma_tipo = Column(String(100), nullable=True)
    dias_anticipacion_compra = Column(Integer, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())
    fecha_actualizacion = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    categoria_directa = relationship("Categoria", foreign_keys=[id_categoria_directa], back_populates="productos_directos")
    subcategoria = relationship("Subcategoria", foreign_keys=[id_subcategoria], back_populates="productos")
    
    precios_proveedor = relationship("PrecioProveedor", back_populates="producto", cascade="all, delete-orphan")
    detalles_compra = relationship("DetalleCompra", back_populates="producto", cascade="all, delete-orphan") 
    
    def __repr__(self):
        return f"<Producto(id={self.id_producto}, nombre='{self.nombre_producto}', sku='{self.sku}')>"

class Proveedor(Base):
    __tablename__ = 'proveedores'
    id_proveedor = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre_proveedor = Column(String(150), nullable=False, index=True)
    contacto_nombre = Column(String(150), nullable=True)
    telefono = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    direccion = Column(Text, nullable=True)
    notas = Column(Text, nullable=True) 
    activo = Column(Boolean, default=True, nullable=False)

    rfc = Column(String(13), nullable=True, index=True)
    razon_social = Column(String(255), nullable=True)
    regimen_fiscal = Column(String(255), nullable=True)
    codigo_postal_fiscal = Column(String(10), nullable=True)
    email_facturacion = Column(String(100), nullable=True)

    precios = relationship("PrecioProveedor", back_populates="proveedor", cascade="all, delete-orphan")
    encabezados_compra = relationship("EncabezadoCompra", back_populates="proveedor", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Proveedor(id={self.id_proveedor}, nombre='{self.nombre_proveedor}', rfc='{self.rfc}')>"

class PrecioProveedor(Base):
    __tablename__ = 'precios_proveedores'
    id_precio_proveedor = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_producto = Column(Integer, ForeignKey('productos.id_producto', ondelete="CASCADE"), nullable=False)
    id_proveedor = Column(Integer, ForeignKey('proveedores.id_proveedor', ondelete="CASCADE"), nullable=False)
    # Este precio_compra en PrecioProveedor debe ser el precio NETO pagado al proveedor.
    precio_compra = Column(DECIMAL(10, 2), nullable=False) 
    unidad_compra_proveedor = Column(String(50), nullable=True) 
    cantidad_minima_compra = Column(Integer, nullable=True)
    fecha_actualizacion_precio = Column(Date, nullable=False, default=func.today())
    notas = Column(Text, nullable=True)
    
    producto = relationship("Producto", back_populates="precios_proveedor")
    proveedor = relationship("Proveedor", back_populates="precios")
    def __repr__(self):
        return f"<PrecioProveedor(prod_id={self.id_producto}, prov_id={self.id_proveedor}, precio={self.precio_compra})>"

class ContadorSKU(Base):
    __tablename__ = 'contadores_sku'
    id_categoria = Column(Integer, ForeignKey('categorias.id_categoria'), primary_key=True)
    ultimo_valor = Column(Integer, nullable=False, default=0)
    categoria = relationship("Categoria", back_populates="contadores_sku")
    def __repr__(self):
        return f"<ContadorSKU(id_cat={self.id_categoria}, val={self.ultimo_valor})>"

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

    def __repr__(self):
        return f"<EncabezadoCompra(id={self.id_encabezado_compra}, prov_id={self.id_proveedor}, num_doc='{self.numero_documento}')>"

class DetalleCompra(Base):
    __tablename__ = 'detalles_compra' 
    id_detalle_compra = Column(Integer, primary_key=True, index=True, autoincrement=True) 
    
    id_encabezado_compra = Column(Integer, ForeignKey('encabezados_compra.id_encabezado_compra'), nullable=False)
    id_producto = Column(Integer, ForeignKey('productos.id_producto'), nullable=False)
    
    cantidad_comprada = Column(DECIMAL(10,2), nullable=False) 
    unidad_compra = Column(String(100), nullable=False) 
    
    # --- NUEVOS CAMPOS PARA DESCUENTO ---
    precio_original_unitario = Column(DECIMAL(10, 2), nullable=True) # Precio de lista o antes de descuento
    monto_descuento_unitario = Column(DECIMAL(10, 2), nullable=True, default=0.00) # Monto del descuento por unidad

    # costo_unitario_compra ahora es el precio NETO (precio_original - descuento)
    costo_unitario_compra = Column(DECIMAL(10, 2), nullable=False) 
    costo_total_item = Column(DECIMAL(12, 2), nullable=False) 
    
    disponibilidad_proveedor = Column(String(50), nullable=True) 
    notas_item = Column(Text, nullable=True) 

    encabezado = relationship("EncabezadoCompra", back_populates="detalles")
    producto = relationship("Producto", back_populates="detalles_compra")

    def __repr__(self):
        return f"<DetalleCompra(id={self.id_detalle_compra}, prod_id={self.id_producto}, enc_id={self.id_encabezado_compra})>"
