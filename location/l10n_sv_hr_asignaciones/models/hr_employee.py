from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    salary_assignment_ids = fields.One2many(
        'hr.salary.assignment', 'employee_id',
        string='Asignaciones salariales'
    )
