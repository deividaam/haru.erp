# /mod_productos/__init__.py
from flask import Blueprint

# Creamos un Blueprint llamado 'productos_bp'.
# El primer argumento es el nombre del Blueprint.
# El segundo argumento, __name__, ayuda a Flask a localizar plantillas y archivos estáticos relativos a este blueprint.
# template_folder='templates' (opcional) si tienes plantillas específicas para este blueprint dentro de mod_productos/templates/
# static_folder='static' (opcional) si tienes archivos estáticos específicos.
productos_bp = Blueprint('productos_bp', __name__,
                        template_folder='templates', # Si decides tener plantillas específicas para productos aquí
                        static_folder='static',      # Si decides tener estáticos específicos para productos aquí
                        url_prefix='/productos')     # Todas las rutas de este blueprint comenzarán con /productos

# Importamos las rutas DESPUÉS de crear el Blueprint para evitar importaciones circulares.
from . import routes
