# /mod_inventario/__init__.py
from flask import Blueprint

# Creamos un Blueprint llamado 'inventario_bp'.
# El prefijo URL '/inventario' se aplicará a todas las rutas definidas en este blueprint.
# Se elimina template_folder ya que las plantillas están en la carpeta global 'templates'.
inventario_bp = Blueprint('inventario_bp', __name__,
                          url_prefix='/inventario')

# Importamos las rutas DESPUÉS de crear el Blueprint para evitar importaciones circulares.
from . import routes
