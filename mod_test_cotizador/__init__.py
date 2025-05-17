# /mod_test_cotizador/__init__.py
from flask import Blueprint

# 1. Definición del Blueprint
test_cotizador_bp = Blueprint('test_cotizador_bp', __name__,
                            template_folder='templates',
                            url_prefix='/test-cotizador')

# 2. Importación de las rutas DESPUÉS de definir el Blueprint
# Esta línea es la que efectivamente registra las rutas definidas en routes.py
# con el test_cotizador_bp que acabamos de crear.
from . import routes
