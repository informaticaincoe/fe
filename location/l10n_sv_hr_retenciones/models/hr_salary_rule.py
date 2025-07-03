from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [Asignaciones - salary]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    # Campo de relación Many2one que vincula un tipo de entrada a la regla salarial
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Tipo de Entrada')

    # # Método para obtener la cuenta contable a partir de un código de configuración
    # def obtener_cuenta_desde_codigo_config(self, clave_config):
    #     """
    #     Este método busca una configuración específica mediante la clave proporcionada
    #     y obtiene la cuenta contable asociada a ese código.
    #
    #     Parámetros:
    #     - clave_config: Clave de la configuración que contiene el código de la cuenta contable.
    #
    #     Retorna:
    #     - Cuenta contable encontrada o False si no se encuentra ninguna cuenta.
    #     """
    #     # Buscar la configuración utilizando la clave proporcionada
    #     config = self.env['res.configuration'].search([('clave', '=', clave_config)], limit=1)
    #
    #     if config and config.value_text:
    #         # Si la configuración se encuentra y tiene un valor asociado, buscar la cuenta contable por el código
    #         cuenta = self.env['account.account'].search([('code', '=', config.value_text)], limit=1)
    #         if cuenta:
    #             return cuenta  # Si se encuentra la cuenta, se retorna
    #     return False  # Si no se encuentra configuración o cuenta, se retorna False

    # @api.model
    # def actualizar_cuentas_reglas(self):
    #     """
    #     Este método recorre las reglas salariales para los códigos específicos (AFP, ISSS, RENTA)
    #     y actualiza la cuenta contable asociada a esas reglas si aún no está configurada.
    #     """
    #
    #     # Configuraciones comunes
    #     default_cuentas = {
    #         'cuenta_salarial_deducciones_credito': 'cuenta_salarial_deducciones',
    #         'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
    #     }
    #
    #     cuentas_empleador = {
    #         'cuenta_salarial_deducciones_credito': 'cuenta_empleador_credito',
    #         'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
    #     }
    #
    #     # Códigos agrupados
    #     deducciones_empleado = [
    #         'AFP', 'ISSS', 'RENTA', 'FSV', 'FONDO_PENSIONES', 'PRESTAMOS', 'VENTA_EMPLEADOS', 'OTROS', 'COMISION'
    #     ]
    #
    #     aportes_patronales = [
    #         'AFP_EMP', 'ISSS_EMP'
    #     ]
    #
    #     # Construcción dinámica
    #     reglas = {}
    #
    #     reglas = {codigo: default_cuentas.copy() for codigo in deducciones_empleado}
    #     reglas.update({codigo: cuentas_empleador.copy() for codigo in aportes_patronales})
    #
    #     # Itera sobre cada código de regla y clave de configuración
    #     for codigo_regla, claves_config in reglas.items():
    #         # Buscar la regla salarial por su código
    #         regla = self.env['hr.salary.rule'].search([('code', '=', codigo_regla)], limit=1)
    #
    #         # Si la regla existe y no tiene configurada una cuenta contable de crédito, actualizarla
    #         if regla:
    #             # Obtener la cuenta contable utilizando la configuración asociada
    #             cuenta_credito = regla.obtener_cuenta_desde_codigo_config(
    #                 claves_config['cuenta_salarial_deducciones_credito'])
    #             cuenta_debito = regla.obtener_cuenta_desde_codigo_config(
    #                 claves_config['cuenta_salarial_deducciones_debito'])
    #
    #             valores = {}
    #             if cuenta_credito and regla.account_credit != cuenta_credito:
    #                 valores['account_credit'] = cuenta_credito.id
    #             if cuenta_debito and regla.account_debit != cuenta_debito:
    #                 valores['account_debit'] = cuenta_debito.id
    #
    #             if valores:
    #                 regla.write(valores)
    #                 _logger.info(f"Actualizada regla {codigo_regla}: {valores}")
    #             else:
    #                 _logger.info(f"Regla {codigo_regla} ya tiene cuentas configuradas correctamente.")

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

        deducciones_empleado = [
            'AFP', 'ISSS', 'RENTA', 'FSV', 'FONDO_PENSIONES', 'PRESTAMOS', 'VENTA_EMPLEADOS', 'OTROS'
        ]

        aportes_patronales = ['AFP_EMP', 'ISSS_EMP']

        reglas = {codigo: default_cuentas.copy() for codigo in deducciones_empleado}
        reglas.update({codigo: cuentas_empleador.copy() for codigo in aportes_patronales})

        config_utils.actualizar_cuentas_retenciones(self.env, reglas)

    @api.model
    def compute_rule_amount(self, rule, contract):
        _logger.warning("⚠️ compute_rule_amount ejecutado para regla: %s", rule.code)
        _logger.info("Cálculo de regla salarial '%s' para contrato ID %s", rule.code, contract.id)

        if rule.code == 'ISSS_EMP':
            resultado = contract.calcular_aporte_patronal('isss')
            _logger.info("Resultado del cálculo ISSS_EMP: %.2f", resultado)
            return resultado

        elif rule.code == 'AFP_EMP':
            resultado = contract.calcular_aporte_patronal('afp')
            _logger.info("Resultado del cálculo AFP_EMP: %.2f", resultado)
            return resultado

        _logger.info("Regla sin cálculo personalizado. Retornando 0.0")
        return 0.0
