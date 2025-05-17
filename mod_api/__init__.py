# /mod_api/__init__.py
from flask import Blueprint

# Creamos un Blueprint llamado 'api_bp'.
# El prefijo URL '/api' se aplicará a todas las rutas definidas en este blueprint.
api_bp = Blueprint('api_bp', __name__, url_prefix='/api')

# Importamos las rutas DESPUÉS de crear el Blueprint para evitar importaciones circulares.
from . import routes
