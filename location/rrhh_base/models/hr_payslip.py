from odoo import models, fields, api, _

class HrPayslip(models.Model):
    _inherit = 'hr.attendance'

    attendance_type = fields.Selection([
        ('full', 'Asistencia Completa'),
        ('partial_justified', 'Parcial Justificada'),
        ('partial_unjustified', 'Parcial No Justificada'),
        ('absent_with_deduction', 'Inasistencia con Descuento'),
        ('absent_no_deduction', 'Inasistencia sin Descuento'),
    ], default='full')

    descontar = fields.Boolean(string="Aplicar Descuento", default=False)
    horas_a_descontar = fields.Float(string="Horas a Descontar", help="Solo si es asistencia parcial.")

    # date = fields.Date(compute='_compute_date', store=True)

    def action_print_payslip(self):
        return self.env.ref('rrhh_base.hr_payslip_report').report_action(self)

