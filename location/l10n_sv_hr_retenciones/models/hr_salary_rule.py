from odoo import models, fields, api

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    # Campo de relación Many2one que vincula un tipo de entrada a la regla salarial
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Tipo de Entrada')

    # Método para obtener la cuenta contable a partir de un código de configuración
    def obtener_cuenta_desde_codigo_config(self, clave_config):
        """
        Este método busca una configuración específica mediante la clave proporcionada
        y obtiene la cuenta contable asociada a ese código.

        Parámetros:
        - clave_config: Clave de la configuración que contiene el código de la cuenta contable.

        Retorna:
        - Cuenta contable encontrada o False si no se encuentra ninguna cuenta.
        """
        # Buscar la configuración utilizando la clave proporcionada
        config = self.env['res.configuration'].search([('clave', '=', clave_config)], limit=1)

        if config and config.value_text:
            # Si la configuración se encuentra y tiene un valor asociado, buscar la cuenta contable por el código
            cuenta = self.env['account.account'].search([('code', '=', config.value_text)], limit=1)
            if cuenta:
                return cuenta  # Si se encuentra la cuenta, se retorna
        return False  # Si no se encuentra configuración o cuenta, se retorna False

    @api.model
    def actualizar_cuentas_reglas(self):
        """
        Este método recorre las reglas salariales para los códigos específicos (AFP, ISSS, RENTA)
        y actualiza la cuenta contable asociada a esas reglas si aún no está configurada.
        """
        # Diccionario que mapea el código de la regla salarial con la clave de configuración correspondiente
        reglas = {
            # Deducciones del empleado
            'AFP': {
                'cuenta_salarial_deducciones_credito': 'cuenta_salarial_deducciones',
                'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
            },
            'ISSS': {
                'cuenta_salarial_deducciones_credito': 'cuenta_salarial_deducciones',
                'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
            },
            'RENTA': {
                'cuenta_salarial_deducciones_credito': 'cuenta_salarial_deducciones',
                'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
            },
            # Aportes patronales
            'AFP_EMP': {
                'cuenta_salarial_deducciones_credito': 'cuenta_empleador_credito',
                'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
            },
            'ISSS_EMP': {
                'cuenta_salarial_deducciones_credito': 'cuenta_empleador_credito',
                'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
            },
        }

        # Itera sobre cada código de regla y clave de configuración
        for codigo_regla, claves_config in reglas.items():
            # Buscar la regla salarial por su código
            regla = self.env['hr.salary.rule'].search([('code', '=', codigo_regla)], limit=1)

            # Si la regla existe y no tiene configurada una cuenta contable de crédito, actualizarla
            if regla:
                # Obtener la cuenta contable utilizando la configuración asociada
                cuenta_credito = regla.obtener_cuenta_desde_codigo_config(claves_config['cuenta_salarial_deducciones_credito'])
                if cuenta_credito:
                    regla.write({'account_credit': cuenta_credito.id})  # Actualiza la cuenta contable de crédito

                # Obtener la cuenta de débito utilizando la configuración asociada
                cuenta_debito = regla.obtener_cuenta_desde_codigo_config(claves_config['cuenta_salarial_deducciones_debito'])
                if cuenta_debito:
                    regla.write({'account_debit': cuenta_debito.id})  # Actualiza la cuenta contable de débito

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
