from odoo import _, api, fields, models

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    primer_nombre = fields.Char(related='employee_id.primer_nombre', readonly=True)
    segundo_nombre = fields.Char(related='employee_id.segundo_nombre', readonly=True)
    primer_apellido = fields.Char(related='employee_id.primer_apellido', readonly=True)
    segundo_apellido = fields.Char(related='employee_id.segundo_apellido', readonly=True)
    apellido_casada = fields.Char(related='employee_id.apellido_casada', readonly=True)

