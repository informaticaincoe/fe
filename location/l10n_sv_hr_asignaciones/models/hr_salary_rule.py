from odoo import models, api

import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [Asignaciones - salary]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    @api.model
    def actualizar_cuentas_asignaciones(self):
        """
        Actualiza las cuentas contables relacionadas con las reglas salariales
        de asignaciones específicas (COMISION, VIATICO, BONO, OVERTIME).

        La actualización se basa en un diccionario de cuentas predefinidas y
        usa la función genérica 'actualizar_cuentas_reglas_generico' del módulo
        'config_utils' para aplicar los cambios.

        Esta función registra el proceso mediante logs para facilitar la depuración.
        """
        _logger.info("Iniciando actualización de cuentas para asignaciones salariales...")

        # Diccionario base que relaciona tipos de cuenta contable
        cuentas = constants.CUENTAS_ASIGNACIONES
        _logger.debug("Cuentas configuradas: %s", cuentas)

        # Códigos de reglas salariales a las que se aplicará la actualización
        codigos = constants.CODIGOS_REGLAS_ASIGNACIONES
        _logger.debug("Códigos de reglas a procesar: %s", codigos)

        # Construcción del diccionario de reglas para la actualización
        reglas = {codigo: cuentas.copy() for codigo in codigos}
        _logger.debug("Reglas generadas para actualización: %s", reglas)

        try:
            # Llamada a la función genérica que aplica la actualización en el entorno
            config_utils.actualizar_cuentas_reglas_generico(self.env, reglas)
            _logger.info("Actualización de cuentas de asignaciones completada correctamente.")
        except Exception as e:
            # Captura y registro de cualquier error durante la actualización
            _logger.exception("Error actualizando cuentas de asignaciones: %s", str(e))
