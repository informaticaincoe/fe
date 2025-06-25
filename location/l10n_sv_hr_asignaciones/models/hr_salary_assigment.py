from odoo import models, fields


class HrSalaryAssignment(models.Model):
    _name = 'hr.salary.assignment'
    _description = 'Salary Assignment'

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    tipo = fields.Selection([
        ('hora_extra', 'Hora extra'),
        ('comision', 'Comisión'),
        ('viaticos', 'Viáticos'),
        ('bono', 'Bono'),
    ], string='Tipo')
    monto = fields.Float("Monto", required=True)
    periodo = fields.Date("Periodo", required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Histórico (Boleta)', help="Si se desea vincular con un recibo de pago.")
