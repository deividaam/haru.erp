# /mod_cotizaciones/__init__.py
from flask import Blueprint

# Creamos un Blueprint llamado 'cotizaciones_bp'.
# El prefijo URL '/cotizaciones' se aplicará a todas las rutas definidas en este blueprint.
cotizaciones_bp = Blueprint('cotizaciones_bp', __name__,
                            template_folder='templates', # Opcional, si tienes plantillas específicas aquí
                            url_prefix='/cotizaciones')

# Importamos las rutas DESPUÉS de crear el Blueprint.
from . import routes

