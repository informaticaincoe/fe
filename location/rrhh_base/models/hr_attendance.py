from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [Asignaciones[]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None
    config_utils = None

class HrPayslip(models.Model):
    _inherit = 'hr.attendance'

    # def action_descargar_plantilla_asistencia(self):
    #
    #     # Busca el archivo adjunto con la plantilla
    #     attachment = self.env['ir.attachment'].search([('name', '=', constants.NOMBRE_PLANTILLA_ASISTENCIA)], limit=1)
    #     if not attachment:
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'title': 'Error',
    #                 'message': 'No se encontró la plantilla para descargar.',
    #                 'type': 'danger',
    #                 'sticky': False,
    #             }
    #         }
    #     # Retorna la acción para descargar el archivo
    #     return {
    #         'type': 'ir.actions.act_url',
    #          'url': '/web/content/my_module/static/plantillas/plantilla_asistencia.xlsx?download=true',
    #         'target': 'self',
    #     }
