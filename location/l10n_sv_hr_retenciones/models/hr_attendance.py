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

    # Mapeo entre tipos de asistencia y códigos de entradas de nómina
    tipo_asistencia = fields.Selection([
        ('ASISTENCIA', 'Asistencia'),
        ('PERMISO_SG', 'Permiso sin goce'),
        ('PERMISO_CG', 'Permiso con goce'),
        ('VACACIONES', 'Vacaciones'),
        ('INCAPACIDAD', 'Incapacidad'),
        ('FALTA_INJ', 'Falta injustificada'),
        ('MATERNIDAD', 'Maternidad'),
        ('PATERNIDAD', 'Paternidad'),
        ('MATRIMONIO', 'Matrimonio'),
        ('DISCIPLINARIA', 'Medida disciplinaria'),
    ], string="Tipo de Asistencia", default="ASISTENCIA")

    se_paga = fields.Boolean(string="¿Se paga?", default=True)

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
