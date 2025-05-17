# /mod_admin_servicios/__init__.py
from flask import Blueprint

# Creamos un Blueprint llamado 'admin_servicios_bp'.
# El prefijo URL '/admin/servicios' se aplicará a todas las rutas definidas en este blueprint.
admin_servicios_bp = Blueprint('admin_servicios_bp', __name__,
                               template_folder='templates', # Opcional, si tienes plantillas específicas aquí
                               url_prefix='/admin/servicios')

# Importamos las rutas DESPUÉS de crear el Blueprint.
from . import routes
