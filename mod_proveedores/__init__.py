# /mod_proveedores/__init__.py
from flask import Blueprint

# Creamos un Blueprint llamado 'proveedores_bp'.
# El prefijo URL '/proveedores' se aplicará a todas las rutas definidas en este blueprint.
proveedores_bp = Blueprint('proveedores_bp', __name__,
                           template_folder='templates', # Opcional, si tienes plantillas específicas aquí
                           url_prefix='/proveedores')

# Importamos las rutas DESPUÉS de crear el Blueprint.
from . import routes
