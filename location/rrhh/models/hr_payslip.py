from odoo import models
import logging

_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_print_payslip(self):
        _logger.info("SIT | Ejecutando action_print_payslip personalizado de rrhh")
        return self.env.ref('rrhh.hr_payslip_report_incoe').report_action(self)