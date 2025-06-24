from odoo import models, fields, api

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    input_type_id = fields.Many2one('hr.payslip.input.type', string='Tipo de Entrada')

    #Obtiene el codigo de la cuenta contable que se aplicara en la regla salarial
    def obtener_cuenta_desde_codigo_config(self, clave_config):
        config = self.env['res.configuration'].search([('clave', '=', clave_config)], limit=1)
        if config and config.value_text:
            cuenta = self.env['account.account'].search([('code', '=', config.value_text)], limit=1)
            if cuenta:
                return cuenta
        return False

    @api.model
    def actualizar_cuentas_reglas(self):
        reglas = {
            'AFP': 'cuenta_salarial_deducciones',
            'ISSS': 'cuenta_salarial_deducciones',
            'RENTA': 'cuenta_salarial_deducciones',
        }

        for codigo_regla, clave_config in reglas.items():
            regla = self.env['hr.salary.rule'].search([('code', '=', codigo_regla)], limit=1)
            if regla and not regla.account_credit:
                cuenta = regla.obtener_cuenta_desde_codigo_config(clave_config)
                if cuenta:
                    regla.write({'account_credit': cuenta.id})
