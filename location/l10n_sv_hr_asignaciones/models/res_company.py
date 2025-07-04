from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    pago_incaf = fields.Boolean(
        string='Paga INCAF',
        help='Marca esta opción si la empresa realiza aportes al INCAF con base en la planilla de los empleados.',
        default=True
    )
