from odoo import models, fields

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    amount_select = fields.Selection(
        selection_add=[('renta', 'Renta')],
        ondelete={'renta': 'set default'}
    )

    def _compute_rule(self, localdict):
        self.ensure_one()
        if self.amount_select == 'renta':
            result = localdict['contract'].calcular_deduccion_renta()
            localdict['result'] = result
            return result, 1.0, 100.0
        else:
            return super()._compute_rule(localdict)