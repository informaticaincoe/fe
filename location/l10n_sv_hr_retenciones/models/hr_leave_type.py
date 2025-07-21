from odoo import models, fields, api

class HrLeaveType(models.Model):
    _inherit = "hr.leave.type"

    is_vacation = fields.Boolean(
        string="¿Es vacaciones?",
        help="Marca este tipo como vacaciones para mostrar campos relacionados"
    )
