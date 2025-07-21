from odoo import api, fields, models
from odoo.exceptions import ValidationError

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    vacation_type = fields.Selection([
        ('total', 'Vacaciones completas'),
        ('partial', 'Vacaciones parciales'),
    ], string="Tipo de vacaciones")

    @api.constrains('vacation_type', 'request_date_from', 'request_date_to')
    def _check_partial_vacation_days(self):
        for leave in self:
            if leave.vacation_type == 'partial':
                if leave.request_date_from and leave.request_date_to:
                    days = (leave.request_date_to - leave.request_date_from).days + 1
                    if days > 7:
                        raise ValidationError(
                            f"Las vacaciones parciales no pueden exceder 7 días. "
                            f"Has seleccionado {days} días."
                        )
