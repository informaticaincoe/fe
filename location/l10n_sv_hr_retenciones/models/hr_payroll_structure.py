from odoo import models, fields

class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    is_vacation = fields.Boolean(
        string='Planilla de Vacaciones',
        help='Marca esta opción si es planilla de vacaciones.',
        default=False
    )
