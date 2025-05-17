# /mod_ordenes_compra/__init__.py
from flask import Blueprint

ordenes_compra_bp = Blueprint('ordenes_compra_bp', __name__,
                               template_folder='templates',
                               url_prefix='/ordenes-compra')

from . import routes
