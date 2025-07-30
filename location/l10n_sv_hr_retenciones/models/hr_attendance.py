from odoo import models, fields

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    def action_descargar_plantilla(self):
        attachment = self.env['ir.attachment'].search([
            ('name', '=', 'plantilla_asistencia.xlsx'),
            ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        ], limit=1)

        if not attachment:
            raise UserError("No se encontró la plantilla de asistencia.")

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
