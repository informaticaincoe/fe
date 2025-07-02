from . import models
#from .hooks import crear_asistencias_faltantes
#from .hooks import post_init_configuracion_reglas
from .hooks import ejecutar_hooks_post_init

import logging
_logger = logging.getLogger(__name__)

def post_init_hook(cr, registry):
    from odoo.api import Environment, SUPERUSER_ID
    _logger.info("Ejecutando post_init_hook para actualizar cuentas de retenciones")
    env = Environment(cr, SUPERUSER_ID, {})
    env['hr.salary.rule'].actualizar_cuentas_asignaciones()  # o actualizar_cuentas_asignaciones()
    _logger.info("Actualización de cuentas de retenciones completada")