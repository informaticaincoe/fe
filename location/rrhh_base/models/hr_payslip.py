from odoo import models

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_print_payslip(self):
        # Usa tu nuevo template
        return self.env.ref('rrhh_base.hr_payslip_report').report_action(self)
