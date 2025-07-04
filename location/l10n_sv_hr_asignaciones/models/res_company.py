from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    overtime_percentage = fields.Float(
        string='Porcentaje de horas extra (%)',
        help='Porcentaje a aplicar sobre el salario hora para calcular el valor de horas extra.',
        default=1.0
    )
