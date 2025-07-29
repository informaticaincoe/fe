from odoo import api, fields, models
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # vacation_full = fields.Boolean(
    #     string="Vacaciones completas",
    #     help="Si está marcado, las vacaciones son completas; si no, son parciales."
    # )
