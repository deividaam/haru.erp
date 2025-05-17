# /mod_proyectos/__init__.py
from flask import Blueprint

# Creamos un Blueprint llamado 'proyectos_bp'.
# El prefijo URL '/proyectos' se aplicará a todas las rutas definidas en este blueprint.
proyectos_bp = Blueprint('proyectos_bp', __name__,
                         template_folder='templates', # Opcional, si tienes plantillas específicas aquí
                         url_prefix='/proyectos')

# Importamos las rutas DESPUÉS de crear el Blueprint.
from . import routes
