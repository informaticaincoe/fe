from odoo import api, fields, models
from odoo.exceptions import ValidationError

import logging

import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def action_descargar_plantilla_tiempo_personal(self):
        attachment = self.env['ir.attachment'].search([
            ('name', '=', 'plantilla_tiempo_personal.xlsx'),
            ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        ], limit=1)

        if not attachment:
            raise UserError("No se encontró la plantilla de deducciones.")

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
