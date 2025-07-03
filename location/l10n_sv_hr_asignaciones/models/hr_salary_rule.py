from odoo import models, api

import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [Asignaciones - salary]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    @api.model
    def actualizar_cuentas_asignaciones(self):
        _logger.info("Iniciando actualización de cuentas para asignaciones salariales...")

        cuentas = {
            'cuenta_salarial_deducciones_credito': 'cuenta_salarial_deducciones',
            'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
        }
        _logger.debug("Cuentas configuradas: %s", cuentas)

        codigos = ['COMISION', 'VIATICO', 'BONO', 'OVERTIME']
        _logger.debug("Códigos de reglas a procesar: %s", codigos)

        reglas = {codigo: cuentas.copy() for codigo in codigos}
        _logger.debug("Reglas generadas para actualización: %s", reglas)

        try:
            config_utils.actualizar_cuentas_reglas_generico(self.env, reglas)
            _logger.info("Actualización de cuentas de asignaciones completada correctamente.")
        except Exception as e:
            _logger.exception("Error actualizando cuentas de asignaciones: %s", str(e))
