# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
# ... (otros imports de Flask y SQLAlchemy se mantienen) ...
from database import SessionLocal
# ... (imports de utils_carga y modelos se mantienen) ...
from datetime import date, datetime, timezone # timedelta y Decimal si se usan en las rutas restantes
from decimal import Decimal

# Importar TODOS los modelos (ya lo tienes)
from models import (
    Producto, Categoria, Subcategoria, Proveedor,
    PrecioProveedor, EncabezadoCompra, DetalleCompra, ContadorSKU,
    Proyecto, Cotizacion, ItemCotizacion, DetalleComponenteSeleccionado,
    TipoServicioBase, VarianteServicioConfig, GrupoComponenteConfig, OpcionComponenteServicio
)


app = Flask(__name__)
app.secret_key = os.urandom(24)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename): # Mantener si es global o mover a utils
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_now():
    return {'now': datetime.now(timezone.utc)}

# --- REGISTRAR BLUEPRINTS ---
from mod_productos import productos_bp
app.register_blueprint(productos_bp)

from mod_proveedores import proveedores_bp
app.register_blueprint(proveedores_bp)

from mod_proyectos import proyectos_bp
app.register_blueprint(proyectos_bp)

from mod_cotizaciones import cotizaciones_bp
app.register_blueprint(cotizaciones_bp)

from mod_admin_servicios import admin_servicios_bp
app.register_blueprint(admin_servicios_bp)

from mod_compras import compras_bp # 
app.register_blueprint(compras_bp)   

from mod_test_cotizador import test_cotizador_bp
app.register_blueprint(test_cotizador_bp)

from mod_ordenes_compra import ordenes_compra_bp
app.register_blueprint(ordenes_compra_bp)

from mod_api import api_bp
app.register_blueprint(api_bp)

from mod_inventario import inventario_bp 
app.register_blueprint(inventario_bp)

# CAMPOS_OBLIGATORIOS_FORM_POR_CATEGORIA y TODAS_LAS_CATEGORIAS_NOMBRES_PRODUCTOS_INTERNOS
# (Se mantienen si son globales)
CAMPOS_OBLIGATORIOS_FORM_POR_CATEGORIA = {
    "Dulces/Golosinas": {
        "fields": ["unidad_medida_base", "sabor"],
        "labels": ["Unidad de Medida Base", "Sabor"]
    },
    "Globos": {
        "fields": ["unidad_medida_base", "color", "tamano_pulgadas"],
        "labels": ["Unidad de Medida Base", "Color", "Tamaño (Pulgadas)"]
    },
}
TODAS_LAS_CATEGORIAS_NOMBRES_PRODUCTOAS_INTERNOS = ["Dulces/Golosinas", "Globos", "Decoración", "Display", "Servicios Directos"]


# --- RUTA PRINCIPAL ---
@app.route('/')
def index():
    return redirect(url_for('proyectos_bp.vista_listar_proyectos'))


# Las rutas de Compras han sido movidas a mod_compras/routes.py

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
