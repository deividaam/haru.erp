# /mod_compras/__init__.py
from flask import Blueprint

# Creamos un Blueprint llamado 'compras_bp'.
# El prefijo URL '/compras' se aplicará a todas las rutas definidas en este blueprint.
compras_bp = Blueprint('compras_bp', __name__,
                       template_folder='templates', # Opcional, si tienes plantillas específicas aquí
                       url_prefix='/compras')

# Importamos las rutas DESPUÉS de crear el Blueprint.
from . import routes
