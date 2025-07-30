from odoo import models, fields, api
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

    # Campo de relación Many2one que vincula un tipo de entrada a la regla salarial
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Tipo de Entrada')

    @api.model
    def actualizar_cuentas_retenciones(self):
        # Cuentas por defecto para deducciones del empleado
        default_cuentas = {
            'cuenta_salarial_deducciones_credito': 'cuenta_salarial_deducciones',
            'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
        }

        # Cuentas para aportes patronales
        cuentas_empleador = {
            'cuenta_salarial_deducciones_credito': 'cuenta_empleador_credito',
            'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
        }

        # Cuentas para salario de fin de semana
        cuentas_fin_semana = {
            'cuenta_salarial_deducciones_credito': 'cuenta_salarial_credito_fs',
            'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito_fs',
        }

        # Armar diccionario de reglas y cuentas
        reglas = {codigo: default_cuentas.copy() for codigo in constants.CONST_CODIGOS_DEDUCCIONES_EMPLEADO}
        reglas.update({codigo: cuentas_empleador.copy() for codigo in constants.CONST_CODIGOS_APORTES_PATRONALES})
        reglas.update({codigo: cuentas_fin_semana.copy() for codigo in constants.REGLASAL_VACACION})

        try:
            config_utils.actualizar_cuentas_reglas_generico(self.env, reglas)
            _logger.info("Actualización de cuentas de asignaciones completada correctamente.")
        except Exception as e:
            _logger.exception("Error actualizando cuentas de asignaciones: %s", str(e))

    @api.model
    def compute_rule_amount(self, rule, contract):
        _logger.warning("compute_rule_amount ejecutado para regla: %s", rule.code)
        _logger.info("Cálculo de regla salarial '%s' para contrato ID %s", rule.code, contract.id)

        if rule.code == constants.COD_ISSS_EMP:
            resultado = contract.calcular_aporte_patronal(constants.TIPO_DED_ISSS)
            _logger.info("Resultado del cálculo ISSS_EMP: %.2f", resultado)
            return resultado

        elif rule.code == constants.COD_AFP_EMP:
            resultado = contract.calcular_aporte_patronal(constants.TIPO_DED_AFP)
            _logger.info("Resultado del cálculo AFP_EMP: %.2f", resultado)
            return resultado

        _logger.info("Regla sin cálculo personalizado. Retornando 0.0")
        return 0.0
