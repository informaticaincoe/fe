from odoo import models, fields

class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    input_type_id = fields.Many2one('hr.payslip.input.type', string='Tipo de entrada para nómina')
